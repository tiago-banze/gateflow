"""
ssl_utils.py
Gera (uma única vez) um certificado HTTPS autoassinado para o servidor
Flask, usando o binário `openssl` já presente no sistema operacional —
sem exigir nenhuma nova dependência pip (evitando pyOpenSSL).

Por quê isso é necessário: navegadores modernos (Chrome, Firefox, Safari)
bloqueiam o acesso à câmera (getUserMedia, usado pelo leitor de QR Code)
em páginas servidas por http:// que não sejam "localhost" — o que
inclui exatamente o cenário deste sistema (acessar o backend pelo IP da
rede local, ex: http://192.168.1.10:5000). Servir a mesma aplicação por
https://, mesmo com um certificado autoassinado (não validado por uma
autoridade certificadora), já é suficiente para o navegador considerar a
origem como "segura" e liberar a câmera — o aviso de "conexão não segura"
que aparece uma vez é esperado e inofensivo neste contexto de rede local
fechada.
"""

import os
import subprocess

import config


def ensure_self_signed_cert():
    """
    Retorna (cert_path, key_path) prontos para uso, gerando o certificado
    na primeira execução se ainda não existir. Se o `openssl` não estiver
    disponível no sistema (ex: alguns Windows sem Git Bash/WSL), retorna
    (None, None) e o chamador deve decidir o que fazer (ex: cair para HTTP).
    """
    cert_path = os.path.join(config.CERTS_DIR, "cert.pem")
    key_path = os.path.join(config.CERTS_DIR, "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    os.makedirs(config.CERTS_DIR, exist_ok=True)

    try:
        subprocess.run(
            [
                "openssl", "req", "-x509",
                "-newkey", "rsa:2048",
                "-keyout", key_path,
                "-out", cert_path,
                "-days", "825",
                "-nodes",
                "-subj", "/CN=checkin-local/O=Sistema de Check-in/C=MZ",
                "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return cert_path, key_path
    except FileNotFoundError:
        # "openssl" não está instalado/no PATH deste sistema
        return None, None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Falha ao gerar (openssl muito antigo, sem suporte a -addext, etc.)
        # — remove qualquer arquivo parcial para não deixar um certificado corrompido
        for path in (cert_path, key_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        return None, None
