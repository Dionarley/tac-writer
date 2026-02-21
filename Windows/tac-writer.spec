# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import re   # IMPORTANTE PARA A CORREÇÃO DO CACHE
from pathlib import Path

MINGW = os.path.join(os.environ.get('MSYSTEM_PREFIX', '/mingw64'))

# Coletar DLLs GTK4 necessárias
gtk_bins = os.path.join(MINGW, 'bin')
gtk_dlls = []
for f in os.listdir(gtk_bins):
    if f.endswith('.dll'):
        gtk_dlls.append((os.path.join(gtk_bins, f), '.'))

# GObject Introspection typelibs
typelib_dir = os.path.join(MINGW, 'lib', 'girepository-1.0')
typelibs = [(os.path.join(typelib_dir, f), 'lib/girepository-1.0') 
            for f in os.listdir(typelib_dir) if f.endswith('.typelib')]

# GLib schemas
schemas_dir = os.path.join(MINGW, 'share', 'glib-2.0', 'schemas')
schemas = [(os.path.join(schemas_dir, 'gschemas.compiled'), 'share/glib-2.0/schemas')]

# Ícones Adwaita (essenciais para GTK4)
icon_dir = os.path.join(MINGW, 'share', 'icons', 'Adwaita')
icons = []
if os.path.exists(icon_dir):
    for root, dirs, files in os.walk(icon_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            icons.append((src, dst))

# Hicolor icons
hicolor_dir = os.path.join(MINGW, 'share', 'icons', 'hicolor')
if os.path.exists(hicolor_dir):
    for root, dirs, files in os.walk(hicolor_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            icons.append((src, dst))

# GDK Pixbuf loaders (SEM DUPLICAÇÃO)
pixbuf_dir = os.path.join(MINGW, 'lib', 'gdk-pixbuf-2.0')
pixbufs = []
if os.path.exists(pixbuf_dir):
    for root, dirs, files in os.walk(pixbuf_dir):
        for f in files:
            if f == 'loaders.cache':
                continue # Ignoramos o arquivo original quebrado
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            pixbufs.append((src, dst))


# CORREÇÃO CRÍTICA DO CACHE DE IMAGENS (SVGs) PARA WINDOWS
cache_src = os.path.join(pixbuf_dir, '2.10.0', 'loaders.cache')
patched_cache_dir = os.path.abspath(os.path.join('build', 'patched_cache'))
os.makedirs(patched_cache_dir, exist_ok=True)
patched_cache_file = os.path.join(patched_cache_dir, 'loaders.cache')

if os.path.exists(cache_src):
    with open(cache_src, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Substitui os caminhos absolutos do MSYS2 pelos nomes relativos das DLLs
    content = re.sub(r'"[^"]*/([^/]+\.dll)"', r'"\1"', content)
    
    with open(patched_cache_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    pixbufs.append((patched_cache_file, 'lib/gdk-pixbuf-2.0/2.10.0'))

# Arquivos nativos do GTK4 (Temas, Componentes Visuais e Shaders)
gtk4_dir = os.path.join(MINGW, 'share', 'gtk-4.0')
gtk4_data = []
if os.path.exists(gtk4_dir):
    for root, dirs, files in os.walk(gtk4_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            gtk4_data.append((src, dst))

# Arquivos do próprio app
app_data = []

# Locales do app
locale_dir = 'locales'
if os.path.exists(locale_dir):
    for root, dirs, files in os.walk(locale_dir):
        for f in files:
            src = os.path.join(root, f)
            app_data.append((src, root))

# Outros recursos (CSS, ícones do app, etc.)
for resource_dir in ['resources', 'assets', 'data']:
    if os.path.exists(resource_dir):
        for root, dirs, files in os.walk(resource_dir):
            for f in files:
                src = os.path.join(root, f)
                app_data.append((src, root))

# Juntar todos os data files (agora inclui o gtk4_data)
all_datas = (gtk_dlls + typelibs + schemas + icons + pixbufs + gtk4_data + app_data)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=all_datas + [('icons/hicolor', 'share/icons/hicolor')],
    hiddenimports=[
        'gi',
        'gi.overrides',
        'gi.overrides.Gtk',
        'gi.overrides.Gdk',
        'gi.overrides.GLib',
        'gi.overrides.GObject',
        'gi.overrides.Gio',
        'gi.overrides.Pango',
        'gi.overrides.GdkPixbuf',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Gio',
        'gi.repository.Pango',
        'gi.repository.GdkPixbuf',
        'gi.repository.Adw',
        'enchant',
        'json',
        'sqlite3',
        'pathlib',
        'platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TacWriter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icons/hicolor/scalable/apps/tac-writer.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TacWriter',
)