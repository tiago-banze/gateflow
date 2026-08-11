"""
generate_site_qr.py
Gera o QR Code OFICIAL do sistema -- o único que deve ir para
material impresso (banners, convites, placas na portaria etc.).

Ao contrário dos QR Codes de convidado (gerados por qrcode_utils.py, um
por pessoa, para o check-in), este QR Code é ÚNICO para todo o evento:
ele codifica apenas a URL pública do site. Qualquer pessoa que
escaneá-lo cai na landing page / página de RSVP, exatamente como se
tivesse digitado o endereço manualmente no navegador.

Uso:
    python generate_site_qr.py
    python generate_site_qr.py --url https://meu-evento.vercel.app
    python generate_site_qr.py --url https://meu-evento.vercel.app --out convite_qr.png --size 20

Se --url não for informado, o script tenta usar a variável de ambiente
GATEFLOW_PUBLIC_BASE_URL (a mesma já lida por config.py em produção).
"""

import argparse
import os
import sys

import qrcode
from qrcode.constants import ERROR_CORRECT_H


def generate_site_qr(url, output_path="site_qr.png", box_size=12, border=4, logo_path=None):
    """
    Gera e salva a imagem PNG do QR Code apontando para `url`.

    - error_correction=ERROR_CORRECT_H (30% de tolerância a dano/sujeira):
      nível mais alto disponível, recomendado para material impresso que
      vai circular fisicamente (pode amassar, molhar, ser fotografado em
      ângulo etc.) -- diferente do QR Code de convidado (que fica numa
      tela/PDF controlado e usa nível M).
    - `logo_path`, se informado, cola uma logo pequena no centro do QR
      Code (a alta correção de erro do ERROR_CORRECT_H permite isso sem
      quebrar a leitura, desde que a logo não ocupe mais que ~20-25% da
      área).
    """
    if not url or not url.strip():
        raise ValueError("URL vazia -- informe --url ou configure GATEFLOW_PUBLIC_BASE_URL.")

    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"URL inválida (precisa começar com http:// ou https://): {url!r}")

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")

    if logo_path:
        from PIL import Image

        logo = Image.open(logo_path).convert("RGBA")
        qr_width, qr_height = img.size
        logo_max_size = qr_width // 5
        logo.thumbnail((logo_max_size, logo_max_size))
        pos = (
            (qr_width - logo.size[0]) // 2,
            (qr_height - logo.size[1]) // 2,
        )
        img.paste(logo, pos, mask=logo)

    img.save(output_path)
    return output_path


def _main():
    parser = argparse.ArgumentParser(description="Gera o QR Code oficial do site GateFlow.")
    parser.add_argument(
        "--url",
        default=os.environ.get("GATEFLOW_PUBLIC_BASE_URL", "").strip(),
        help="URL pública do site (ex: https://meu-evento.vercel.app). "
             "Se omitido, usa a variável de ambiente GATEFLOW_PUBLIC_BASE_URL.",
    )
    parser.add_argument("--out", default="site_qr.png", help="Caminho do arquivo PNG de saída.")
    parser.add_argument("--size", type=int, default=12, help="Tamanho de cada 'módulo' do QR Code em pixels.")
    parser.add_argument("--logo", default=None, help="Caminho opcional de uma logo para colar no centro do QR Code.")
    args = parser.parse_args()

    try:
        path = generate_site_qr(args.url, output_path=args.out, box_size=args.size, logo_path=args.logo)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"QR Code gerado com sucesso: {os.path.abspath(path)}")
    print(f"Conteúdo codificado: {args.url}")


if __name__ == "__main__":
    _main()
