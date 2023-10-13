from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import aiohttp
import markdown
import tenacity

import randovania
from randovania import VERSION
from randovania.cli import database
from randovania.games import default_data
from randovania.games.game import RandovaniaGame
from randovania.lib import json_lib
from randovania.lib.enum_lib import iterate_enum

_ROOT_FOLDER = Path(__file__).parents[1]
_NINTENDONT_DOWNLOAD_URL = "https://github.com/randovania/Nintendont/releases/download/v5-multiworld/boot.dol"
zip_folder = f"randovania-{VERSION}"


def is_production():
    return os.getenv("PRODUCTION", "false") == "true"


def open_zip(platform_name: str) -> zipfile.ZipFile:
    return zipfile.ZipFile(
        _ROOT_FOLDER.joinpath(f"dist/{zip_folder}-{platform_name}.zip"), "w", compression=zipfile.ZIP_DEFLATED
    )


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    retry=tenacity.retry_if_exception_type(aiohttp.ClientConnectorError),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=30),
)
async def download_nintendont():
    headers = None
    if "GITHUB_TOKEN" in os.environ:
        headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}

    async with aiohttp.ClientSession(headers=headers) as session:
        print(f"Downloading {_NINTENDONT_DOWNLOAD_URL}")
        async with session.get(_NINTENDONT_DOWNLOAD_URL) as download_response:
            download_response.raise_for_status()
            dol_bytes = await download_response.read()

        final_dol_path = _ROOT_FOLDER.joinpath("randovania", "data", "nintendont", "boot.dol")
        print(f"Saving to {final_dol_path}")
        final_dol_path.write_bytes(dol_bytes)


def write_obfuscator_secret(path: Path, secret: bytes):
    numbers = str(list(secret))
    path.write_text(
        f"""# Generated file
secret = b"".join(
    bytes([x]) for x in
    {numbers}
)
"""
    )


async def main():
    package_folder = Path("dist", "randovania")
    if package_folder.exists():
        shutil.rmtree(package_folder, ignore_errors=False)

    app_folder = Path("dist", "Randovania.app")
    if app_folder.exists():
        shutil.rmtree(app_folder, ignore_errors=False)

    for game in iterate_enum(RandovaniaGame):
        database.export_as_binary(
            default_data.read_json_then_binary(game)[1],
            _ROOT_FOLDER.joinpath("randovania", "data", "binary_data", f"{game.value}.bin"),
        )

    icon_path = randovania.get_icon_path()
    shutil.copyfile(icon_path, icon_path.with_name("executable_icon.ico"))

    if (secret := os.environ.get("OBFUSCATOR_SECRET")) is not None:
        write_obfuscator_secret(
            _ROOT_FOLDER.joinpath("randovania", "lib", "obfuscator_secret.py"),
            secret.encode("ascii"),
        )

    if is_production():
        server_suffix = "randovania"
        client_id = 618134325921316864
    else:
        server_suffix = "randovania-staging"
        client_id = 887825192208969828

    configuration = {
        "discord_client_id": client_id,
        "server_address": f"https://randovania.metroidprime.run/{server_suffix}",
        "socketio_path": f"/{server_suffix}/socket.io",
    }
    json_lib.write_path(_ROOT_FOLDER.joinpath("randovania", "data", "configuration.json"), configuration)

    await download_nintendont()

    # HACK: pyintaller calls lipo/codesign on macOS and frequently timeout in github actions
    # There's also timeouts on Windows so we're expanding this to everyone
    print("Will patch timeout in PyInstaller compat")
    import PyInstaller.compat

    compat_path = Path(PyInstaller.compat.__file__)
    compat_text = compat_path.read_text().replace("timeout=60", "timeout=180")
    compat_path.write_text(compat_text)

    subprocess.run([sys.executable, "-m", "PyInstaller", "randovania.spec"], check=True)

    if platform.system() == "Windows":
        create_windows_zip(package_folder)
    elif platform.system() == "Darwin":
        create_macos_zip(app_folder)
    elif platform.system() == "Linux":
        create_linux_zip(package_folder)
    else:
        raise ValueError(f"Unknown system: {platform.system()}")


def create_windows_zip(package_folder):
    if is_production():
        with open_zip("windows") as release_zip:
            for f in package_folder.glob("**/*"):
                print("Adding", f)
                release_zip.write(f, f"{zip_folder}/{f.relative_to(package_folder)}")

            add_readme_to_zip(release_zip)
    else:
        zip_file = os.fspath(_ROOT_FOLDER.joinpath(f"dist/{zip_folder}-windows.7z"))
        subprocess.run(["7z", "a", "-mx=7", "-myx=7", zip_file, os.fspath(package_folder)], check=True)
        subprocess.run(["7z", "rn", zip_file, os.fspath(package_folder), zip_folder], check=True)


def create_macos_zip(folder_to_pack: Path):
    output = f"dist/{zip_folder}-macos.tar.gz"
    with tarfile.open(_ROOT_FOLDER.joinpath(f"dist/{zip_folder}-macos.tar.gz"), "w:gz") as release_zip:
        print(f"Creating {output} from {folder_to_pack}.")
        release_zip.add(folder_to_pack, f"{zip_folder}/Randovania.app")
        print("Finished.")


def create_linux_zip(folder_to_pack: Path):
    output = _ROOT_FOLDER.joinpath(f"dist/{zip_folder}-linux.tar.gz")
    with tarfile.open(output, "w:gz") as release_zip:
        print(f"Creating {output} from {folder_to_pack}.")
        release_zip.add(folder_to_pack, zip_folder)
        print("Finished.")


def add_readme_to_zip(release_zip):
    with _ROOT_FOLDER.joinpath("README.md").open() as readme_file:
        readme_html = markdown.markdown(readme_file.read())
        release_zip.writestr(zip_folder + "/README.html", readme_html)


if __name__ == "__main__":
    asyncio.run(main())
