#!/usr/bin/env python3
"""
Sincroniza (ou apenas valida) a versão declarada em
usr/share/metainfo/io.github.narayanls.tacwriter.metainfo.xml
com a versão real do release, para evitar builds flatpak "carimbados"
com uma versão antiga (o flatpak-builder lê o <release> mais recente
desse XML e é isso que aparece em `flatpak info`).

A versão do flatpak (ex: 1.4.4-5) é escolhida manualmente por você a
cada release e NÃO tem relação com APP_VERSION do core/config.py
(que é um contador semver separado, usado só na UI/about do app).
Por isso a versão sempre é passada explicitamente via --version,
nunca lida automaticamente de outro arquivo.

Uso típico no pipeline de build, ANTES do flatpak-builder rodar,
a partir da raiz do app (usr/share/tac-writer, mesmo nível de core/ e ui/):

    # Modo padrão: sincroniza (insere um <release> novo se necessário)
    python3 sync_metainfo_version.py --version 1.4.4-6

    # Modo estrito: só valida e falha (exit 1) se estiver desatualizado,
    # sem alterar o arquivo — útil como "gate" de CI antes do build real
    python3 sync_metainfo_version.py --version 1.4.4-6 --check
"""

import argparse
import datetime as dt
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Configuração ─────────────────────────────────────────────────────
# O script fica em usr/share/tac-writer/ (ao lado de core/, ui/, main.py).
# O metainfo fica um nível acima, em usr/share/metainfo/ — ou seja,
# irmão da pasta tac-writer, não filho dela.
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_METAINFO_PATH = (
    SCRIPT_DIR.parent / "metainfo" / "io.github.narayanls.tacwriter.metainfo.xml"
)


def get_latest_metainfo_version(tree: ET.ElementTree) -> str | None:
    """Retorna a versão do primeiro <release> (convenção AppStream:
    mais recente primeiro)."""
    releases = tree.getroot().find("releases")
    if releases is None:
        return None
    first = releases.find("release")
    if first is None:
        return None
    return first.get("version")


def sync_metainfo(metainfo_path: Path, version: str, date: str, check_only: bool) -> bool:
    """Retorna True se já estava sincronizado, False se precisou (ou
    precisaria, em modo --check) de atualização."""
    if not metainfo_path.is_file():
        sys.exit(f"ERRO: metainfo não encontrado em {metainfo_path}")

    tree = ET.parse(metainfo_path)
    latest = get_latest_metainfo_version(tree)

    if latest == version:
        print(f"[sync_metainfo_version] OK: metainfo já está em {version}.")
        return True

    print(
        f"[sync_metainfo_version] DIVERGÊNCIA: metainfo tem "
        f"'{latest}', versão de release informada é '{version}'."
    )

    if check_only:
        return False

    root = tree.getroot()
    releases = root.find("releases")
    if releases is None:
        releases = ET.SubElement(root, "releases")

    # Evita duplicar se essa versão já existir em algum ponto do histórico
    for rel in releases.findall("release"):
        if rel.get("version") == version:
            print(
                f"[sync_metainfo_version] Versão {version} já existe no "
                f"histórico; nada a inserir."
            )
            return False

    new_release = ET.Element("release", {"version": version, "date": date})
    releases.insert(0, new_release)

    # Reindenta o XML inteiro para manter o arquivo legível
    ET.indent(tree, space="  ")
    tree.write(metainfo_path, encoding="UTF-8", xml_declaration=True)

    content = metainfo_path.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        metainfo_path.write_text(content + "\n", encoding="utf-8")

    print(f"[sync_metainfo_version] Inserido <release version=\"{version}\" date=\"{date}\"/>.")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        required=True,
        help="Versão do release do flatpak (ex: 1.4.4-6). Sempre explícita.",
    )
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Data do release no formato YYYY-MM-DD (padrão: hoje)",
    )
    parser.add_argument(
        "--metainfo",
        default=str(DEFAULT_METAINFO_PATH),
        help="Caminho do metainfo.xml (padrão: %(default)s)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Não modifica o arquivo; sai com código 1 se estiver desatualizado "
             "(use isso como gate de CI antes de rodar o flatpak-builder)",
    )
    args = parser.parse_args()

    version = args.version.lstrip("v")
    print(f"[sync_metainfo_version] Versão de release informada: {version}")

    up_to_date = sync_metainfo(Path(args.metainfo), version, args.date, args.check)

    if args.check and not up_to_date:
        sys.exit(
            "\n[sync_metainfo_version] FALHA: metainfo.xml está desatualizado. "
            "Rode sem --check para corrigir, ou o build vai gerar um pacote "
            "com a versão errada em `flatpak info`."
        )


if __name__ == "__main__":
    main()
