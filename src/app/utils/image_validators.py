from django.core.exceptions import ValidationError

try:  # Pillow pode não ser necessário para SVG
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

import io
import re

VALID_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "svg"}
MAX_SIZE = 250  # px


def _validate_svg_square_and_size(content: bytes):
    """Valida (best-effort) se um SVG é aproximadamente quadrado e <= 250x250.
    Não rejeita caso não consiga extrair dimensões (mantém tolerante), apenas se encontrar valores > limite.
    """
    try:
        text = content.decode("utf-8", errors="ignore")
        # Procurar atributos width/height
        width_match = re.search(r'width="(\d+(?:\.\d+)?)"', text)
        height_match = re.search(r'height="(\d+(?:\.\d+)?)"', text)
        viewbox_match = re.search(r'viewBox="([^"]+)"', text)

        width = height = None
        if width_match and height_match:
            width = float(width_match.group(1))
            height = float(height_match.group(1))
        elif viewbox_match:
            parts = viewbox_match.group(1).split()
            if len(parts) == 4:
                # viewBox: min-x min-y width height
                width = float(parts[2])
                height = float(parts[3])

        if width and height:
            if abs(width - height) > 0.5:  # tolerância
                raise ValidationError(
                    f"SVG deve ser aproximadamente quadrado. Dimensões detectadas: {width}x{height}."
                )
            if width > MAX_SIZE or height > MAX_SIZE:
                raise ValidationError(
                    f"SVG excede tamanho máximo de {MAX_SIZE}px (detectado ~{width}x{height})."
                )
    except ValidationError:
        raise
    except Exception:
        # Se não conseguir ler, não bloquear
        return


def validate_logo_file(file_obj):
    """Valida arquivo de logo (PNG/JPG/JPEG/SVG) aplicado em FileField.

    - Extensão deve ser permitida.
    - Para raster (png/jpg/jpeg): quadrada e <= 250x250.
    - Para SVG: tentativa de checar dimensões se disponível.
    """
    if not file_obj:
        return

    name_lower = file_obj.name.lower()
    ext = name_lower.rsplit(".", 1)[-1]
    if ext not in VALID_LOGO_EXTENSIONS:
        raise ValidationError(
            f"Extensão não suportada. Utilize: {', '.join(sorted(VALID_LOGO_EXTENSIONS))}."
        )

    # SVG: validar estrutura básica e (opcional) dimensões
    if ext == "svg":
        # Ler bytes
        content = file_obj.read()
        if b"<svg" not in content[:500].lower():  # verificação simples
            raise ValidationError("Arquivo SVG inválido ou corrompido.")
        _validate_svg_square_and_size(content)
        file_obj.seek(0)
        return

    # Raster: requer Pillow
    if Image is None:
        raise ValidationError(
            "Pillow não disponível para validar imagem raster."
        )

    try:
        # Garantir leitura sem corromper ponteiro
        data = file_obj.read()
        file_obj.seek(0)
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if width != height:
            raise ValidationError(
                f"A logo deve ser quadrada. Dimensões: {width}x{height}px."
            )
        if width > MAX_SIZE or height > MAX_SIZE:
            raise ValidationError(
                f"A logo deve ter no máximo {MAX_SIZE}x{MAX_SIZE}px. Dimensões: {width}x{height}px."
            )
    except ValidationError:
        raise
    except Exception:
        raise ValidationError(
            "Não foi possível processar a imagem. Verifique o arquivo."
        )


# Alias para compatibilidade com migrations antigas que ainda referem validate_logo_image
def validate_logo_image(file_obj):  # pragma: no cover
    return validate_logo_file(file_obj)
