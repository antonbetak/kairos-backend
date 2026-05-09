#!/usr/bin/env python3
"""
Prueba simple del endpoint de login de Google Auth Service.
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv


async def test_health():
    """Test del healthcheck."""
    load_dotenv()
    base_url = os.getenv("GOOGLE_AUTH_URL", "http://localhost:8000")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            response.raise_for_status()
            print(f"✓ Health check OK: {response.json()}")
            return True
        except Exception as e:
            print(f"✗ Health check falló: {e}")
            return False


async def test_login_redirect():
    """Test que el endpoint de login redirige."""
    load_dotenv()
    base_url = os.getenv("GOOGLE_AUTH_URL", "http://localhost:8000")

    async with httpx.AsyncClient(follow_redirects=False) as client:
        try:
            response = await client.get(f"{base_url}/auth/google/login", timeout=5.0)
            if response.status_code == 307:
                location = response.headers.get("location", "")
                if "accounts.google.com" in location:
                    print(f"✓ Login redirect OK: redirige a Google")
                    return True
                else:
                    print(f"✗ Login redirect no apunta a Google: {location}")
                    return False
            else:
                print(f"✗ Login no redirecciona (status {response.status_code})")
                return False
        except Exception as e:
            print(f"✗ Login test falló: {e}")
            return False


async def test_docs():
    """Test que la documentación OpenAPI está disponible."""
    load_dotenv()
    base_url = os.getenv("GOOGLE_AUTH_URL", "http://localhost:8000")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/docs", timeout=5.0)
            response.raise_for_status()
            if "swagger" in response.text.lower():
                print(f"✓ OpenAPI docs OK")
                return True
            else:
                print(f"✗ OpenAPI docs disponible pero parece incompleto")
                return False
        except Exception as e:
            print(f"✗ OpenAPI docs test falló: {e}")
            return False


async def main():
    print("Pruebas del Google Auth Service")
    print("=" * 50)

    results = []
    results.append(("Health Check", await test_health()))
    results.append(("Login Redirect", await test_login_redirect()))
    results.append(("OpenAPI Docs", await test_docs()))

    print("\n" + "=" * 50)
    print("Resumen:")
    passed = sum(1 for _, result in results if result)
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {name}")

    print(f"\nTotal: {passed}/{len(results)} pruebas pasaron")

    if passed == len(results):
        print("\n✓ Todas las pruebas pasaron. El servicio está listo.")
        return 0
    else:
        print("\n✗ Algunas pruebas fallaron. Verifica la configuración.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
