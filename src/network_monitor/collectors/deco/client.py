from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import string
from dataclasses import dataclass
from typing import Any


import httpx
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Util.Padding import pad, unpad

load_dotenv()


@dataclass
class DecoTrafficInfo:
    """Estatística cumulativa de tráfego de um cliente."""

    mac: str
    download_bytes: int | None
    upload_bytes: int | None


@dataclass
class DecoClientInfo:
    """Representa um cliente devolvido pela Deco."""

    name: str
    ip: str
    mac: str
    online: bool
    device_type: str | None = None
    download_speed: int | None = None
    upload_speed: int | None = None
    remain_time: int | None = None
    connection_type: str | None = None
    enable_priority: bool | None = None
    enable_internet: bool | None = None


class DecoAuthError(Exception):
    """Erro de autenticação na Deco."""


class DecoAPIError(Exception):
    """Erro devolvido pela API da Deco."""


class DecoClient:
    """
    Cliente para comunicação com a API local da TP-Link Deco.

    Atualmente implementa:
    - autenticação local;
    - sessão com stok/sysauth;
    - consulta dos clientes ligados à Deco.
    """

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        verify_tls: bool | None = None,
    ) -> None:
        self.host = host or os.getenv("DECO_HOST", "192.168.68.1")
        self.username = username or os.getenv("DECO_USERNAME", "admin")
        self.password = password or os.getenv("DECO_PASSWORD", "")

        self.timeout = timeout or float(os.getenv("DECO_TIMEOUT", "10"))
        self.verify_tls = (
            verify_tls
            if verify_tls is not None
            else os.getenv("DECO_VERIFY_TLS", "false").lower()
            in ("1", "true", "yes", "on")
        )

        self.stok: str | None = None
        self.sysauth: str | None = None

        self._aes_key: str | None = None
        self._aes_iv: str | None = None
        self._rsa_key: RSA.RsaKey | None = None
        self._seq: int | None = None

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    def _url(self, path: str) -> str:
        """Constrói uma URL autenticada com o stok atual."""
        stok = self.stok or ""
        return f"{self.base_url}/cgi-bin/luci/;stok={stok}{path}"

    @staticmethod
    def _random_aes_string(length: int = 16) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _rsa_encrypt_single(
        message: str,
        modulus_hex: str,
        exponent_hex: str,
    ) -> str:
        """
        RSA PKCS#1 v1.5 para mensagens que cabem num único bloco.

        Usado especificamente para cifrar a password no login.
        """

        modulus = int(modulus_hex, 16)
        exponent = int(exponent_hex, 16)

        key = RSA.construct((modulus, exponent))
        cipher = PKCS1_v1_5.new(key)

        encrypted = cipher.encrypt(
            message.encode("utf-8")
        )

        return encrypted.hex().upper()

    @staticmethod
    def _rsa_encrypt_text(
        message: str,
        modulus_hex: str,
        exponent_hex: str,
    ) -> str:
        """
        RSA PKCS#1 v1.5 conforme o protocolo da Deco.

        A implementação JavaScript da TP-Link divide a assinatura
        em blocos de 53 caracteres quando necessário e concatena
        os resultados RSA.
        """
        modulus = int(modulus_hex, 16)
        exponent = int(exponent_hex, 16)

        key = RSA.construct((modulus, exponent))
        cipher = PKCS1_v1_5.new(key)

        chunks = [
            message[i:i + 53]
            for i in range(0, len(message), 53)
        ]

        encrypted_chunks = []

        for chunk in chunks:
            encrypted = cipher.encrypt(
                chunk.encode("utf-8")
            )

            encrypted_chunks.append(
                encrypted.hex()
            )

        return "".join(encrypted_chunks)

    @staticmethod
    def _rsa_encrypt_with_key(
        message: str,
        key: RSA.RsaKey,
    ) -> str:
        """
        RSA PKCS#1 v1.5 usando uma chave pública existente.

        A Deco divide a assinatura em blocos de 53 caracteres
        antes de aplicar RSA.
        """

        cipher = PKCS1_v1_5.new(key)

        raw = message.encode("utf-8")

        block_size = key.size_in_bytes() - 11

        encrypted_chunks = []

        for offset in range(
            0,
            len(raw),
            block_size,
        ):
            chunk = raw[
                offset:offset + block_size
            ]

            encrypted = cipher.encrypt(chunk)

            encrypted_chunks.append(
                encrypted.hex()
            )

        return "".join(encrypted_chunks)

    @staticmethod
    def _aes_encrypt(
        plaintext: str,
        key: str,
        iv: str,
    ) -> str:
        cipher = AES.new(
            key.encode("utf-8"),
            AES.MODE_CBC,
            iv.encode("utf-8"),
        )

        encrypted = cipher.encrypt(
            pad(
                plaintext.encode("utf-8"),
                AES.block_size,
            )
        )

        return base64.b64encode(encrypted).decode("ascii")

    @staticmethod
    def _aes_decrypt(
        ciphertext: str,
        key: str,
        iv: str,
    ) -> str:
        encrypted = base64.b64decode(ciphertext)

        cipher = AES.new(
            key.encode("utf-8"),
            AES.MODE_CBC,
            iv.encode("utf-8"),
        )

        decrypted = cipher.decrypt(encrypted)

        return unpad(
            decrypted,
            AES.block_size,
        ).decode("utf-8")

    def _post(
        self,
        client: httpx.Client,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = client.post(
            self._url(path),
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        error_code = data.get("error_code", 0)

        if error_code not in (0, None):
            raise DecoAPIError(
                f"Deco devolveu error_code={error_code}: {data}"
            )

        return data

    def _get_keys(
        self,
        client: httpx.Client,
    ) -> tuple[str, str]:
        response = client.post(
            f"{self.base_url}/cgi-bin/luci/;stok=/login?form=keys",
            json={"operation": "read"},
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error_code", 0) != 0:
            raise DecoAuthError(
                f"Falha ao obter chave RSA: {data}"
            )

        result = data.get("result", {})
        password_key = result.get("password")

        if (
            not isinstance(password_key, list)
            or len(password_key) != 2
        ):
            raise DecoAuthError(
                "A Deco não devolveu uma chave RSA válida."
            )

        return password_key[0], password_key[1]

    def _get_auth_parameters(
        self,
        client: httpx.Client,
    ) -> tuple[str, str, int]:
        response = client.post(
            f"{self.base_url}/cgi-bin/luci/;stok=/login?form=auth",
            json={"operation": "read"},
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error_code", 0) != 0:
            raise DecoAuthError(
                f"Falha ao obter parâmetros de autenticação: {data}"
            )

        result = data.get("result", {})

        key = result.get("key")
        seq = result.get("seq")

        if (
            not isinstance(key, list)
            or len(key) != 2
            or seq is None
        ):
            raise DecoAuthError(
                "A Deco não devolveu os parâmetros de autenticação esperados."
            )

        return key[0], key[1], int(seq)

    @staticmethod
    def _extract_sysauth(
        response: httpx.Response,
    ) -> str | None:
        """
        Extrai o cookie sysauth do Set-Cookie da resposta HTTP.
        """

        for header in response.headers.get_list("set-cookie"):
            if header.startswith("sysauth="):
                return header.split("=", 1)[1].split(";", 1)[0]

        return None

    def _login(
        self,
        client: httpx.Client,
    ) -> None:
        if not self.password:
            raise DecoAuthError(
                "DECO_PASSWORD não está configurada."
            )

        # ---------------------------------------------------------
        # 1. Obter RSA para cifrar a password
        # ---------------------------------------------------------
        password_modulus, password_exponent = self._get_keys(client)

        encrypted_password = self._rsa_encrypt_single(
            self.password,
            password_modulus,
            password_exponent,
        )

        # ---------------------------------------------------------
        # 2. Obter RSA + sequence para a sessão AES
        # ---------------------------------------------------------
        sign_modulus, sign_exponent, seq = (
            self._get_auth_parameters(client)
        )

        self._rsa_key = RSA.construct(
            (
                int(sign_modulus, 16),
                int(sign_exponent, 16),
            )
        )

        self._seq = seq

        # ---------------------------------------------------------
        # 3. Gerar AES
        # ---------------------------------------------------------
        self._aes_key = self._random_aes_string()
        self._aes_iv = self._random_aes_string()

        # ---------------------------------------------------------
        # 4. Hash username + password
        # ---------------------------------------------------------
        password_hash = hashlib.md5(
            f"{self.username}{self.password}".encode("utf-8")
        ).hexdigest()

        # ---------------------------------------------------------
        # 5. Password cifrada dentro do payload de login
        # ---------------------------------------------------------
        login_payload = {
            "params": {
                "password": encrypted_password.upper(),
            },
            "operation": "login",
        }

        payload_json = json.dumps(
            login_payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        encrypted_data = self._aes_encrypt(
            payload_json,
            self._aes_key,
            self._aes_iv,
        )

        # ---------------------------------------------------------
        # 6. Construir assinatura
        # ---------------------------------------------------------
        signature_text = (
            f"k={self._aes_key}"
            f"&i={self._aes_iv}"
            f"&h={password_hash}"
            f"&s={self._seq + len(encrypted_data)}"
        )

        sign = self._rsa_encrypt_text(
            signature_text,
            sign_modulus,
            sign_exponent,
        )

        # ---------------------------------------------------------
        # 7. Enviar login
        # ---------------------------------------------------------
        response = client.post(
            f"{self.base_url}/cgi-bin/luci/;stok=/login",
            params={"form": "login"},
            data={
                "sign": sign,
                "data": encrypted_data,
            },
            headers={
                "Accept": (
                    "application/json, "
                    "text/javascript, */*; q=0.01"
                ),
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/webpages/index.html",
            },
        )

        response.raise_for_status()

        response_data = response.json()

        if response_data.get("error_code", 0) != 0:
            raise DecoAuthError(
                f"Autenticação rejeitada pela Deco: {response_data}"
            )

        # ---------------------------------------------------------
        # 8. Desencriptar resposta do login
        # ---------------------------------------------------------
        encrypted_response = response_data.get("data")

        if not encrypted_response:
            raise DecoAuthError(
                "A Deco aceitou o login, mas não devolveu dados cifrados."
            )

        try:
            decrypted_response = self._aes_decrypt(
                encrypted_response,
                self._aes_key,
                self._aes_iv,
            )

            login = json.loads(decrypted_response)

            if not isinstance(login, dict):
                raise DecoAuthError(
                    "Resposta desencriptada do login não é um objeto JSON."
                )

            # O probe funcional da Deco aceita o resultado em result
            # ou, conforme a versão, diretamente em data.
            login_result = login.get("result") or login.get("data") or {}

            # O erro interno está dentro da resposta AES.
            # Não o confundimos com um login aceite só porque a
            # resposta HTTP externa teve error_code=0.
            inner_error = login.get("error_code")
            if inner_error not in (None, 0):
                raise DecoAuthError(
                    f"Deco rejeitou o login: error_code={inner_error}, "
                    f"msg={login.get('msg', 'sem mensagem')}"
                )
        except Exception as exc:
            raise DecoAuthError(
                f"Não foi possível desencriptar a resposta do login: {exc}"
            ) from exc

        # ---------------------------------------------------------
        # 9. Extrair STOK
        # ---------------------------------------------------------
        stok = None

        if isinstance(login_result, dict):
            stok = login_result.get("stok")

            if not stok:
                stok = login_result.get("token")

        if not stok:
            raise DecoAuthError(
                "Login aceite, mas o resultado desencriptado "
                "não contém stok."
            )

        self.stok = stok

        # ---------------------------------------------------------
        # 10. Extrair sysauth
        # ---------------------------------------------------------
        sysauth = self._extract_sysauth(response)

        if not sysauth:
            raise DecoAuthError(
                "Login aceite, mas a Deco não devolveu "
                "o cookie sysauth."
            )

        self.sysauth = sysauth

        # ---------------------------------------------------------
        # 10. sysauth através dos cookies
        # ---------------------------------------------------------
        sysauth = client.cookies.get("sysauth")

        if sysauth:
            self.sysauth = sysauth

    def _decrypt_response(
        self,
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Desencripta respostas AES da Deco.
        """
        if not self._aes_key or not self._aes_iv:
            raise DecoAuthError(
                "Sessão AES não está inicializada."
            )

        encrypted_data = response_data.get("data")

        if not encrypted_data:
            return response_data

        plaintext = self._aes_decrypt(
            encrypted_data,
            self._aes_key,
            self._aes_iv,
        )

        decoded = json.loads(plaintext)

        if not isinstance(decoded, dict):
            raise DecoAPIError(
                "Resposta desencriptada da Deco não é um objeto JSON."
            )

        return decoded

    def authenticate(self) -> None:
        """
        Autentica na Deco e cria uma sessão válida.
        """
        self.stok = None
        self.sysauth = None
        self._aes_key = None
        self._aes_iv = None
        self._rsa_key = None
        self._seq = None

        with httpx.Client(
            timeout=self.timeout,
            verify=self.verify_tls,
            follow_redirects=True,
        ) as client:
            self._login(client)

    def get_clients(self) -> list[DecoClientInfo]:
        """
        Obtém a lista atual de clientes da Deco.
        """

        if not self.stok:
            self.authenticate()

        if not self._aes_key or not self._aes_iv:
            raise DecoAuthError(
                "Sessão AES não está disponível."
            )

        if not self._rsa_key:
            raise DecoAuthError(
                "Chave RSA da sessão não está disponível."
            )

        if self._seq is None:
            raise DecoAuthError(
                "Sequence da sessão não está disponível."
            )

        if not self.sysauth:
            raise DecoAuthError(
                "Cookie sysauth não está disponível."
            )

        # ---------------------------------------------------------
        # Payload exatamente como no probe funcional
        # ---------------------------------------------------------
        payload = {
            "operation": "read",
            "params": {
                "device_mac": "default",
            },
        }

        payload_json = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        # ---------------------------------------------------------
        # AES
        # ---------------------------------------------------------
        encrypted_data = self._aes_encrypt(
            payload_json,
            self._aes_key,
            self._aes_iv,
        )

        # ---------------------------------------------------------
        # Assinatura para pedidos normais
        #
        # Ao contrário do login, aqui o tpEncrypt.js não inclui
        # k= e i= na assinatura.
        # ---------------------------------------------------------
        password_hash = hashlib.md5(
            f"{self.username}{self.password}".encode("utf-8")
        ).hexdigest()

        signature_text = (
            f"h={password_hash}"
            f"&s={self._seq + len(encrypted_data)}"
        )

        # O RSA da sessão tem de ser usado em blocos.
        encrypted_signature = self._rsa_encrypt_with_key(
            signature_text,
            self._rsa_key,
        )

        # ---------------------------------------------------------
        # Pedido
        # ---------------------------------------------------------
        with httpx.Client(
            timeout=self.timeout,
            verify=self.verify_tls,
            follow_redirects=True,
        ) as client:

            client.cookies.set(
                "sysauth",
                self.sysauth,
                domain=self.host,
            )

            response = client.post(
                self._url(
                    "/admin/client?form=client_list"
                ),
                data={
                    "sign": encrypted_signature,
                    "data": encrypted_data,
                },
                headers={
                    "Accept": (
                        "application/json, "
                        "text/javascript, */*; q=0.01"
                    ),
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": self.base_url,
                    "Referer": (
                        f"{self.base_url}/webpages/index.html"
                    ),
                },
            )

            response.raise_for_status()

            raw = response.json()

            if raw.get("error_code", 0) != 0:
                raise DecoAPIError(
                    f"Falha ao obter clientes: {raw}"
                )

            # -----------------------------------------------------
            # Desencriptar resposta
            # -----------------------------------------------------
            data = self._decrypt_response(raw)

            result = data.get("result", {})

            client_list = (
                result.get("client_list", [])
                if isinstance(result, dict)
                else []
            )

            if not isinstance(client_list, list):
                raise DecoAPIError(
                    "A Deco não devolveu client_list como lista."
                )

            # -----------------------------------------------------
            # Converter para os nossos modelos
            # -----------------------------------------------------
            clients: list[DecoClientInfo] = []

            for item in client_list:
                clients.append(
                    DecoClientInfo(
                        name=self._decode_name(
                            item.get("name", "")
                        ),
                        ip=item.get("ip", ""),
                        mac=item.get("mac", ""),
                        online=bool(
                            item.get("online", False)
                        ),
                        device_type=item.get("client_type"),
                        download_speed=item.get("down_speed"),
                        upload_speed=item.get("up_speed"),
                        remain_time=item.get("remainTime"),
                        connection_type=item.get(
                            "connectionType"
                        ),
                        enable_priority=item.get(
                            "enablePriority"
                        ),
                        enable_internet=item.get(
                            "enableInternet"
                        ),
                    )
                )

            return clients

    def get_traffic_stats(self) -> list[DecoTrafficInfo]:
        """Obtém contadores cumulativos de tráfego por cliente.

        A Deco expõe estes dados em ``/admin/client?form=traffic_stat``
        com ``operation=list``. O endpoint devolve contadores cumulativos;
        o Network Monitor calcula posteriormente os deltas entre recolhas.
        """
        if not self.stok:
            self.authenticate()

        if not self._aes_key or not self._aes_iv or not self._rsa_key or self._seq is None:
            raise DecoAuthError("Sessão Deco incompleta para consulta de tráfego.")
        if not self.sysauth:
            raise DecoAuthError("Cookie sysauth não está disponível.")

        payload = {
            "operation": "list",
            "params": {"device_mac": "default"},
        }
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        encrypted_data = self._aes_encrypt(payload_json, self._aes_key, self._aes_iv)
        password_hash = hashlib.md5(f"{self.username}{self.password}".encode("utf-8")).hexdigest()
        signature_text = f"h={password_hash}&s={self._seq + len(encrypted_data)}"
        encrypted_signature = self._rsa_encrypt_with_key(signature_text, self._rsa_key)

        with httpx.Client(timeout=self.timeout, verify=self.verify_tls, follow_redirects=True) as client:
            client.cookies.set("sysauth", self.sysauth, domain=self.host)
            response = client.post(
                self._url("/admin/client?form=traffic_stat"),
                data={"sign": encrypted_signature, "data": encrypted_data},
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/webpages/index.html",
                },
            )
            response.raise_for_status()
            raw = response.json()

        if raw.get("error_code", 0) not in (0, None):
            raise DecoAPIError(f"Falha ao obter tráfego: {raw}")

        data = self._decrypt_response(raw)

        print("\n===== TRAFFIC STAT RAW =====")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("===== FIM TRAFFIC STAT RAW =====\n")

        result = data.get("result", {})

        # O firmware/versão pode devolver a lista diretamente em result ou
        # dentro de traffic_stat/client_list/traffic_list. Aceitamos as formas
        # conhecidas para manter o collector tolerante a pequenas diferenças.
        items: Any = result
        if isinstance(result, dict):
            for key in ("traffic_stat", "client_list", "traffic_list", "list"):
                if isinstance(result.get(key), list):
                    items = result[key]
                    break
            else:
                items = []

        if not isinstance(items, list):
            raise DecoAPIError("A Deco não devolveu uma lista de estatísticas de tráfego.")

        stats: list[DecoTrafficInfo] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mac = item.get("mac") or item.get("device_mac") or item.get("client_mac")
            if not mac:
                continue

            # retx_byte = bytes transmitidos (upload); rerx_byte = bytes
            # recebidos (download). Mantemos fallback para nomes explícitos.
            upload = item.get("retx_byte", item.get("tx_bytes", item.get("upload_bytes")))
            download = item.get("rerx_byte", item.get("rx_bytes", item.get("download_bytes")))

            def as_int(value: Any) -> int | None:
                try:
                    return int(value) if value is not None else None
                except (TypeError, ValueError):
                    return None

            stats.append(
                DecoTrafficInfo(
                    mac=str(mac).replace(":", "-").upper(),
                    download_bytes=as_int(download),
                    upload_bytes=as_int(upload),
                )
            )

        return stats

    @staticmethod
    def _decode_name(value: Any) -> str:
        """
        Os nomes dos clientes da Deco aparecem em Base64.
        """
        if not isinstance(value, str) or not value:
            return ""

        try:
            decoded = base64.b64decode(
                value,
                validate=True,
            )

            return decoded.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return value