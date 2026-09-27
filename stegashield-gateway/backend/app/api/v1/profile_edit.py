import base64
from io import BytesIO
import warnings

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.core.auth import Principal, current_user
from backend.app.services.gateway import Gateway, get_gateway

router = APIRouter()
MAX_UPLOAD = 2 * 1024 * 1024
MAX_IMAGE = 100000


def normalise_photo(data: bytes) -> bytes:
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(413, 'Choose a non-empty picture up to 2 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ('JPEG', 'PNG') or getattr(source, 'n_frames', 1) != 1:
                    raise HTTPException(415, 'Choose a static JPEG or PNG picture.')
                if max(source.size) > 4096 or min(source.size) < 1:
                    raise HTTPException(413, 'Picture dimensions must not exceed 4096 pixels.')
                source.load()
                fixed = ImageOps.exif_transpose(source)
                fixed.thumbnail((256, 256))
                rgba = fixed.convert('RGBA')
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                output = BytesIO()
                clean.save(output, 'JPEG', quality=85)
                result = output.getvalue()
                if len(result) > MAX_IMAGE:
                    raise HTTPException(413, 'Picture is too complex. Choose a smaller image.')
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'The picture could not be read safely.') from None


@router.post('/auth/profile')
async def update_profile(request: Request, display_name: str = Form(...),
                         remove_photo: bool = Form(False), photo: UploadFile | None = File(None),
                         user: Principal = Depends(current_user), gateway: Gateway = Depends(get_gateway)):
    form = await request.form()
    if set(form.keys()) - {'display_name', 'remove_photo', 'photo'} or any(len(form.getlist(k)) > 1 for k in form):
        raise HTTPException(422, 'Only display name and profile picture can be changed.')
    name = display_name.strip()
    if not 1 <= len(name) <= 120:
        raise HTTPException(422, 'Display name must contain 1 to 120 characters.')
    if photo and remove_photo:
        raise HTTPException(422, 'Choose a replacement picture or remove the current one, not both.')
    encoded = None
    if photo:
        try:
            data = await photo.read(MAX_UPLOAD + 1)
            encoded = base64.b64encode(await run_in_threadpool(normalise_photo, data)).decode('ascii')
        finally:
            await photo.close()
    result = await run_in_threadpool(gateway.request, 'POST', '/rest/v1/rpc/update_profile_details', json={
        'p_user_id': str(user.id), 'p_display_name': name,
        'p_change_photo': photo is not None or remove_photo, 'p_image_base64': encoded})
    if result is not True:
        raise HTTPException(503, 'Profile update was not acknowledged. Reload to check your profile.')
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})


@router.get('/auth/profile/photo')
def profile_photo(user: Principal = Depends(current_user), gateway: Gateway = Depends(get_gateway)):
    rows = gateway.rows('profile_photos', user, user_id=f'eq.{user.id}', select='user_id,image_base64', limit='1')
    if not rows:
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})
    if len(rows) != 1 or rows[0].get('user_id') != str(user.id):
        raise HTTPException(503, 'Profile picture unavailable.')
    try:
        encoded = rows[0]['image_base64']
        if len(encoded) > 140000:
            raise ValueError()
        data = base64.b64decode(encoded, validate=True)
        if len(data) > MAX_IMAGE or not data.startswith(b'\xff\xd8\xff'):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Profile picture unavailable.') from None
    return Response(data, media_type='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
