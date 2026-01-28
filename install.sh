#!/bin/bash

# ==========================================
# CONFIGURAÇÕES GERAIS
# ==========================================
APP_NAME="tac-writer"
GITHUB_USER="narayanls"
VERSION_TAG="v1.2.6-3"     # Tag da Release no Github
VERSION_FILE="1.2.6-3"    # Versão no nome do arquivo
DEBUG_MODE="1"            # 1 = Debug SUSE Ativo

# Dependências OpenSUSE
SUSE_DEPS="typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 libadwaita-1-0 python313 python313-gobject python313-reportlab python313-pygtkspellcheck python313-pyenchant python313-Pillow python313-requests python313-pypdf python313-PyLaTeX gettext-runtime liberation-fonts myspell-pt_BR myspell-en_US myspell-es"

# Definição dos Arquivos
FILE_DEB="${APP_NAME}_${VERSION_FILE}_amd64.deb" 
FILE_RPM="${APP_NAME}-${VERSION_FILE}-1.x86_64.rpm"

# URLs
BASE_URL="https://github.com/$GITHUB_USER/$APP_NAME/releases/download/$VERSION_TAG"
URL_DEB="$BASE_URL/$FILE_DEB"
URL_RPM="$BASE_URL/$FILE_RPM"

# Diretório temporário
TEMP_DIR="/tmp/$APP_NAME-install"
mkdir -p "$TEMP_DIR"

# Arquivos de Controle
FLAG_DONE="$TEMP_DIR/process_done"
FLAG_CLOSE="$TEMP_DIR/close_terminal"
LOG_FILE="$TEMP_DIR/process.log"

# ==========================================
# PREPARAÇÃO E AUTO-INSTALAÇÃO DO ZENITY
# ==========================================

if [ -f /etc/os-release ]; then . /etc/os-release; else echo "Erro: /etc/os-release não encontrado."; exit 1; fi
DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
DISTRO_LIKE_ID=$(echo "$ID_LIKE" | tr '[:upper:]' '[:lower:]')

ensure_zenity() {
    if ! command -v zenity &> /dev/null; then
        echo "=========================================================="
        echo " AVISO: O 'zenity' (interface gráfica) não foi encontrado."
        echo " O instalador tentará baixá-lo automaticamente agora."
        echo "=========================================================="
        echo ""
        
        INSTALL_ZENITY_CMD=""
        
        if [[ "$DISTRO_ID" == *"arch"* ]] || [[ "$DISTRO_LIKE_ID" == *"arch"* ]] || [[ "$DISTRO_ID" == "cachyos" ]]; then
            INSTALL_ZENITY_CMD="sudo pacman -S --noconfirm zenity"
        elif [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_LIKE_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]] || [[ "$DISTRO_LIKE_ID" == *"ubuntu"* ]]; then
            INSTALL_ZENITY_CMD="sudo apt-get update && sudo apt-get install -y zenity"
        elif [[ "$DISTRO_ID" == *"fedora"* ]] || [[ "$DISTRO_LIKE_ID" == *"fedora"* ]]; then
            INSTALL_ZENITY_CMD="sudo dnf install -y zenity"
        elif [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]]; then
            INSTALL_ZENITY_CMD="sudo zypper --non-interactive install -y zenity"
        fi

        if [ -n "$INSTALL_ZENITY_CMD" ]; then
            echo "Executando: $INSTALL_ZENITY_CMD"
            eval "$INSTALL_ZENITY_CMD"
            if ! command -v zenity &> /dev/null; then
                echo "ERRO: Falha ao instalar Zenity. Instale manualmente."
                read -p "Enter para sair..."
                exit 1
            fi
            sleep 2
        else
            echo "ERRO: Distro não suportada para auto-instalação do Zenity."
            exit 1
        fi
    fi
}
ensure_zenity

# ==========================================
# FUNÇÕES E CONTROLE
# ==========================================

cleanup() {
    touch "$FLAG_CLOSE"
    sleep 0.5
    rm -rf "$TEMP_DIR"
    exit
}
trap cleanup SIGINT SIGTERM EXIT

show_error() {
    zenity --error --text="$1" --title="Erro" --width=400
    exit 1
}

detect_terminal() {
    TERM_CMD="x-terminal-emulator -e"
    if ! command -v x-terminal-emulator &> /dev/null; then
        if command -v ashyterm &> /dev/null; then TERM_CMD="ashyterm -e";
        elif command -v zashterminal &> /dev/null; then TERM_CMD="zashterminal -e";
        elif command -v konsole &> /dev/null; then TERM_CMD="konsole -e";
        elif command -v gnome-terminal &> /dev/null; then TERM_CMD="gnome-terminal --"; 
        elif command -v alacritty &> /dev/null; then TERM_CMD="alacritty -e";
        elif command -v kitty &> /dev/null; then TERM_CMD="kitty -e";
        elif command -v xterm &> /dev/null; then TERM_CMD="xterm -e";
        else TERM_CMD=""; fi
    fi
}
detect_terminal

# --- FUNÇÃO CORE: Executa Terminal e Sincroniza ---
run_external_process() {
    local SCRIPT_PATH="$1"
    local TITLE="$2"
    
    rm -f "$FLAG_DONE" "$FLAG_CLOSE"
    
    # Injeta lógica de controle no script do terminal
    cat <<EOF >> "$SCRIPT_PATH"

EXIT_CODE=\$?
echo ""
if [ \$EXIT_CODE -eq 0 ]; then
    echo "SUCESSO! Finalizando..."
    echo "success" > "$FLAG_DONE"
else
    echo "ERRO! Verifique as mensagens acima."
    echo "error" > "$FLAG_DONE"
fi

# Aguarda sinal para fechar
while [ ! -f "$FLAG_CLOSE" ]; do
    sleep 0.5
done
exit \$EXIT_CODE
EOF
    
    chmod +x "$SCRIPT_PATH"
    $TERM_CMD "$SCRIPT_PATH" &
    
    # Zenity monitora o progresso
    (
        echo "0"; echo "# Inicializando..."
        sleep 1
        while [ ! -f "$FLAG_DONE" ]; do
            echo "# Processando... Acompanhe no terminal."; sleep 1
        done
        echo "100"
    ) | zenity --progress --title="$TITLE" --pulsate --auto-close --width=400
    
    # Verifica o resultado
    if [ -f "$FLAG_DONE" ]; then
        STATUS=$(cat "$FLAG_DONE")
        
        if [ "$STATUS" == "success" ]; then
            
            #--- FOCO E FECHAMENTO DO TERMINAL ---
            touch "$FLAG_CLOSE"
            
            sleep 0.5 
            
            zenity --info --text="Processo concluído com sucesso!\n\nO aplicativo já está disponível no menu." --title="Sucesso" --width=350
        else
            zenity --error --text="Ocorreu um erro no terminal.\nVerifique a saída antes de fechar esta mensagem." --width=400
            
            touch "$FLAG_CLOSE"
        fi
    else
        zenity --warning --text="Processo interrompido." --width=300
        touch "$FLAG_CLOSE"
    fi
    
    sleep 0.5
    exit 0
}

# ==========================================
# LÓGICA DE INSTALAÇÃO
# ==========================================

PKG_TYPE="unknown"
if [[ "$DISTRO_ID" == *"arch"* ]] || [[ "$DISTRO_LIKE_ID" == *"arch"* ]] || [[ "$DISTRO_ID" == "cachyos" ]]; then PKG_TYPE="arch"
elif [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_LIKE_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]] || [[ "$DISTRO_LIKE_ID" == *"ubuntu"* ]]; then PKG_TYPE="deb"; DOWNLOAD_URL="$URL_DEB"; FILENAME="$FILE_DEB"; INSTALL_CMD="apt-get install -y"
elif [[ "$DISTRO_ID" == *"fedora"* ]] || [[ "$DISTRO_LIKE_ID" == *"fedora"* ]] || [[ "$DISTRO_ID" == *"rhel"* ]] || [[ "$DISTRO_ID" == *"centos"* ]] || [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]]; then PKG_TYPE="rpm"; DOWNLOAD_URL="$URL_RPM"; FILENAME="$FILE_RPM"; INSTALL_CMD="dnf install -y"
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]]; then INSTALL_CMD="zypper --non-interactive install -y --allow-unsigned-rpm"; fi
fi

if [ "$PKG_TYPE" == "unknown" ]; then show_error "Distro não suportada: $ID"; fi

zenity --question --title="Instalador $APP_NAME" \
    --text="Instalador <b>$APP_NAME v$VERSION_FILE</b>.\nSistema: <b>${PRETTY_NAME}</b>\n\nDeseja instalar?" \
    --ok-label="Instalar" --cancel-label="Cancelar" --width=400 || exit 0

# --- ARCH LINUX (AUR) ---
if [ "$PKG_TYPE" == "arch" ]; then
    AUR_HELPER=""
    if command -v yay &> /dev/null; then AUR_HELPER="yay"; elif command -v paru &> /dev/null; then AUR_HELPER="paru"; fi
    if [ -z "$AUR_HELPER" ]; then show_error "yay ou paru não encontrados."; fi
    if [ -z "$TERM_CMD" ]; then show_error "Nenhum terminal encontrado."; fi

    AUR_SCRIPT="$TEMP_DIR/aur_install.sh"
    echo "#!/bin/bash" > "$AUR_SCRIPT"
    echo "echo '=== INSTALAÇÃO VIA AUR ==='" >> "$AUR_SCRIPT"
    echo "$AUR_HELPER -S $APP_NAME --noconfirm" >> "$AUR_SCRIPT"
    
    run_external_process "$AUR_SCRIPT" "Instalando via AUR..."
    exit 0
fi

# --- DOWNLOAD ---
FILE_PATH="$TEMP_DIR/$FILENAME"
(wget -O "$FILE_PATH" "$DOWNLOAD_URL" 2>&1 | sed -u 's/.* \([0-9]\+%\)\ \+\([0-9.]\+.\) \(.*\)/\1\n# Baixando \2\/s ETA \3/' | zenity --progress --title="Baixando..." --auto-close --width=400) || exit 0
if [ ! -s "$FILE_PATH" ]; then show_error "Erro no download."; fi

# --- INSTALAÇÃO PADRÃO (DEB/RPM) ---
INSTALL_LOG="$TEMP_DIR/install.log"
SUCCESS_FLAG="$TEMP_DIR/success"

(
    echo "10"; echo "# Aguarde enquanto instalamos..."
    if pkexec $INSTALL_CMD "$FILE_PATH" > "$INSTALL_LOG" 2>&1; then echo "100"; touch "$SUCCESS_FLAG"
    else echo "100"; fi
) | zenity --progress --title="Instalando..." --pulsate --auto-close --no-cancel --width=400

# --- TRATAMENTO SUSE (FIX) ---
if [ -f "$SUCCESS_FLAG" ]; then
    zenity --info --text="Instalação concluída com sucesso! \nTac Writer já está no menu do sistema." --width=300
else
    IS_SUSE=0
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]]; then IS_SUSE=1; fi
    
    if [ $IS_SUSE -eq 1 ]; then
        zenity --question --title="Dependências OpenSUSE" \
            --text="A instalação padrão falhou.\n\nDeseja abrir o terminal para corrigir dependências e forçar a instalação?" \
            --ok-label="Corrigir no Terminal" --cancel-label="Cancelar" --width=500
            
        if [ $? -eq 0 ] && [ ! -z "$TERM_CMD" ]; then
            FIX_SCRIPT="$TEMP_DIR/suse_fix.sh"
            echo "#!/bin/bash" > "$FIX_SCRIPT"
            echo "echo '=== CORREÇÃO DE DEPENDÊNCIAS SUSE ==='" >> "$FIX_SCRIPT"
            echo "echo '1. Instalando Dependências...'" >> "$FIX_SCRIPT"
            echo "sudo zypper --non-interactive install -y $SUSE_DEPS" >> "$FIX_SCRIPT"
            echo "echo ''" >> "$FIX_SCRIPT"
            echo "echo '2. Instalando App (Force RPM)...'" >> "$FIX_SCRIPT"
            echo "sudo rpm -Uvh --nodeps --force '$FILE_PATH'" >> "$FIX_SCRIPT"
            
            run_external_process "$FIX_SCRIPT" "Corrigindo Dependências..."
            exit 0
        fi
    fi

    ERROR_MSG=$(tail -n 10 "$INSTALL_LOG")
    zenity --error --text="Falha na instalação.\n\n$ERROR_MSG" --width=600
fi

exit 0
