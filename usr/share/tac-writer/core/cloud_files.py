"""
TAC - Sincronização dos arquivos de imagem com o Dropbox.

O banco guarda apenas os metadados da imagem. O arquivo em si vive em:

    config.data_dir / 'images' / <project_id> / <filename>

Sobre nomes de arquivo
----------------------
Duas armadilhas ditam o desenho deste módulo:

1. O Dropbox expõe dois campos de caminho. O path_lower é minúsculo e
   serve só para comparação; o path_display preserva o nome real. Gravar
   o arquivo local usando o path_lower renomeia a imagem e o app deixa
   de encontrá-la. Pior: procurar um arquivo local pelo nome minúsculo
   falha silenciosamente no Linux, e a imagem nunca é enviada.

2. Acentos podem chegar em NFC (ã como um código) ou NFD (a + til como
   dois códigos). São strings diferentes para o Python e nomes de arquivo
   diferentes no Linux, embora idênticos na tela. Comparar sem normalizar
   faz a mesma imagem ser baixada e enviada repetidamente, e o nome
   gravado no banco deixa de bater com o arquivo em disco.

A solução é separar as duas coisas: uma chave normalizada só para
comparar, e o nome real preservado para ler e gravar.
"""

import posixpath
import unicodedata
from pathlib import Path

import dropbox
from dropbox.files import WriteMode, FileMetadata

REMOTE_IMAGES_ROOT = "/images"
CHUNK_THRESHOLD = 8 * 1024 * 1024


def _fold(name: str) -> str:
    """Chave de comparação: normaliza acentos e ignora maiúsculas."""
    return unicodedata.normalize("NFC", name).casefold()


def _remote_listing(dbx, root=REMOTE_IMAGES_ROOT):
    """Mapeia chave normalizada -> caminho remoto real (path_display)."""
    found = {}
    prefix = root.lower() + "/"

    try:
        result = dbx.files_list_folder(root, recursive=True)
    except dropbox.exceptions.ApiError as e:
        # Pasta ainda não existe na nuvem: primeira sincronização.
        if e.error.is_path() and e.error.get_path().is_not_found():
            return found
        raise

    while True:
        for entry in result.entries:
            if not isinstance(entry, FileMetadata):
                continue

            display = entry.path_display or entry.path_lower
            if display.lower().startswith(prefix):
                relative = display[len(root) + 1:]
            else:
                relative = display.lstrip("/")

            if relative:
                found[_fold(relative)] = display

        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)

    return found


def _local_listing(images_root: Path):
    """Mapeia chave normalizada -> Path real no disco."""
    found = {}
    if not images_root.exists():
        return found

    for path in images_root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(images_root).as_posix()
            found[_fold(relative)] = path

    return found


def _upload(dbx, local_path: Path, remote_path: str):
    size = local_path.stat().st_size

    with open(local_path, "rb") as handle:
        if size <= CHUNK_THRESHOLD:
            dbx.files_upload(handle.read(), remote_path, mode=WriteMode("overwrite"))
            return

        session = dbx.files_upload_session_start(handle.read(CHUNK_THRESHOLD))
        cursor = dropbox.files.UploadSessionCursor(
            session_id=session.session_id, offset=handle.tell()
        )
        commit = dropbox.files.CommitInfo(path=remote_path, mode=WriteMode("overwrite"))

        while handle.tell() < size:
            if size - handle.tell() <= CHUNK_THRESHOLD:
                dbx.files_upload_session_finish(
                    handle.read(CHUNK_THRESHOLD), cursor, commit
                )
            else:
                dbx.files_upload_session_append_v2(handle.read(CHUNK_THRESHOLD), cursor)
                cursor.offset = handle.tell()


def sync_images(dbx, images_root: Path, progress=None):
    """
    Une a pasta local de imagens com a pasta remota, nos dois sentidos.

    Retorna (baixadas, enviadas).
    """
    images_root = Path(images_root)
    images_root.mkdir(parents=True, exist_ok=True)

    remote_files = _remote_listing(dbx)
    local_files = _local_listing(images_root)

    downloaded = 0
    uploaded = 0

    # 1. Existe na nuvem e falta aqui.
    for key, remote_display in remote_files.items():
        if key in local_files:
            continue

        # Grava com o nome real, normalizado em NFC.
        relative = unicodedata.normalize(
            "NFC", remote_display[len(REMOTE_IMAGES_ROOT) + 1:]
        )
        destination = images_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            dbx.files_download_to_file(str(destination), remote_display)
            downloaded += 1
            if progress:
                progress(f"Baixando imagem: {destination.name}")
        except Exception as error:
            print(f"[sync_images] falha ao baixar {remote_display}: {error}")

    # 2. Existe aqui e falta na nuvem.
    for key, local_path in local_files.items():
        if key in remote_files:
            continue

        relative = local_path.relative_to(images_root).as_posix()
        remote_path = posixpath.join(
            REMOTE_IMAGES_ROOT, unicodedata.normalize("NFC", relative)
        )

        try:
            _upload(dbx, local_path, remote_path)
            uploaded += 1
            if progress:
                progress(f"Enviando imagem: {local_path.name}")
        except Exception as error:
            print(f"[sync_images] falha ao enviar {relative}: {error}")

    print(f"[sync_images] {len(local_files)} local(is), {len(remote_files)} remota(s), "
          f"{downloaded} baixada(s), {uploaded} enviada(s)")

    return downloaded, uploaded
