package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Configurações
const (
	AppName     = "tac-writer"
	GithubUser  = "narayanls"
	VersionTag  = "v1.2.6-3"
	VersionFile = "1.2.6-3"
	
	// Dependências SUSE
	SuseDeps = "typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 libadwaita-1-0 python313 python313-gobject python313-reportlab python313-pygtkspellcheck python313-pyenchant python313-Pillow python313-requests python313-pypdf python313-PyLaTeX gettext-runtime liberation-fonts myspell-pt_BR myspell-en_US myspell-es"
)

// Estrutura para identificar a distro
type DistroInfo struct {
	ID      string
	IDLike  string
	Pretty  string
}

func main() {
	// 1. Identificar Distro
	distro := getDistroInfo()

	// 2. Garantir Zenity
	ensureZenity(distro)

	// 3. Confirmar Instalação
	if !zenityQuestion(fmt.Sprintf("Instalador %s %s\n\nSistema: %s\n\nDeseja instalar?", AppName, VersionFile, distro.Pretty)) {
		os.Exit(0)
	}

	// 4. Definir URLs e Comandos
	var downloadUrl, fileName, installCmd string

	tempDir := os.TempDir()

	// Lógica de Seleção
	if strings.Contains(distro.ID, "arch") || strings.Contains(distro.IDLike, "arch") || distro.ID == "cachyos" {
		fileName = fmt.Sprintf("%s-%s-any.pkg.tar.zst", AppName, VersionFile)
		downloadUrl = fmt.Sprintf("https://github.com/%s/%s/releases/download/%s/%s", GithubUser, AppName, VersionTag, fileName)
		installCmd = "pacman -U --noconfirm"
	} else if strings.Contains(distro.ID, "debian") || strings.Contains(distro.IDLike, "debian") || strings.Contains(distro.ID, "ubuntu") {
		fileName = fmt.Sprintf("%s_%s_amd64.deb", AppName, VersionFile)
		downloadUrl = fmt.Sprintf("https://github.com/%s/%s/releases/download/%s/%s", GithubUser, AppName, VersionTag, fileName)
		installCmd = "apt-get install -y"
	} else if strings.Contains(distro.ID, "fedora") || strings.Contains(distro.IDLike, "fedora") || strings.Contains(distro.ID, "rhel") || strings.Contains(distro.ID, "suse") || strings.Contains(distro.IDLike, "suse") {
		fileName = fmt.Sprintf("%s-%s.x86_64.rpm", AppName, VersionFile)
		downloadUrl = fmt.Sprintf("https://github.com/%s/%s/releases/download/%s/%s", GithubUser, AppName, VersionTag, fileName)
		installCmd = "dnf install -y"
		
		if strings.Contains(distro.ID, "suse") || strings.Contains(distro.IDLike, "suse") {
			installCmd = "zypper --non-interactive install -y --allow-unsigned-rpm"
		}
	} else {
		zenityError("Distribuição não suportada: " + distro.ID)
		os.Exit(1)
	}

	filePath := filepath.Join(tempDir, fileName)

	// 5. Download com Barra de Progresso
	err := downloadFile(downloadUrl, filePath)
	if err != nil {
		zenityError("Erro no download:\n" + err.Error())
		os.Exit(1)
	}

	// 6. Instalação com pkexec
	success := installPackage(installCmd, filePath)

	// 7. Correção SUSE (Se falhar a primeira tentativa)
	if !success && (strings.Contains(distro.ID, "suse") || strings.Contains(distro.IDLike, "suse")) {
		if zenityQuestion("A instalação padrão falhou.\nDeseja corrigir dependências e tentar novamente?") {
			// Script composto para corrigir dependências
			cmdFix := fmt.Sprintf("zypper --non-interactive install -y %s; rpm -Uvh --nodeps --force '%s'", SuseDeps, filePath)
			fixSuccess := runPkexecBash(cmdFix, "Corrigindo e Instalando...")
			
			if fixSuccess {
				success = true
			}
		}
	}

	// 8. Finalização
	if success {
		zenityInfo("Instalação concluída com sucesso!\nO aplicativo já está no menu.")
	} else {
		zenityError("Falha na instalação. Ocorreu um erro ao executar o comando de instalação.")
	}

	// Limpeza
	os.Remove(filePath)
}

// --- FUNÇÕES AUXILIARES ---

func getDistroInfo() DistroInfo {
	file, err := os.Open("/etc/os-release")
	if err != nil {
		return DistroInfo{ID: "unknown", Pretty: "Linux Unknown"}
	}
	defer file.Close()

	info := DistroInfo{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "ID=") {
			info.ID = strings.Trim(strings.TrimPrefix(line, "ID="), "\"")
		} else if strings.HasPrefix(line, "ID_LIKE=") {
			info.IDLike = strings.Trim(strings.TrimPrefix(line, "ID_LIKE="), "\"")
		} else if strings.HasPrefix(line, "PRETTY_NAME=") {
			info.Pretty = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), "\"")
		}
	}
	// Normaliza para lowercase
	info.ID = strings.ToLower(info.ID)
	info.IDLike = strings.ToLower(info.IDLike)
	return info
}

func ensureZenity(d DistroInfo) {
	_, err := exec.LookPath("zenity")
	if err == nil {
		return
	}

	var cmd string
	if strings.Contains(d.ID, "arch") || strings.Contains(d.IDLike, "arch") {
		cmd = "pacman -S --noconfirm zenity"
	} else if strings.Contains(d.ID, "debian") || strings.Contains(d.IDLike, "debian") {
		cmd = "apt-get update && apt-get install -y zenity"
	} else if strings.Contains(d.ID, "fedora") {
		cmd = "dnf install -y zenity"
	} else if strings.Contains(d.ID, "suse") {
		cmd = "zypper --non-interactive install -y zenity"
	}

	if cmd != "" {
		fullCmd := exec.Command("pkexec", "bash", "-c", cmd)
		fullCmd.Run()
	}
}

func downloadFile(url string, filepath string) error {
	// Inicia o wget enviando output para o zenity progress
	cmd := exec.Command("bash", "-c", fmt.Sprintf("wget -O '%s' '%s' 2>&1 | sed -u 's/.* \\([0-9]\\+%%\\) \\+\\([0-9.]\\+.\\) \\(.*\\)/\\1\\n# Baixando \\2\\/s ETA \\3/' | zenity --progress --title='Baixando...' --auto-close --width=400", filepath, url))
	return cmd.Run()
}

func installPackage(installCmd, filePath string) bool {
	// pkexec roda o comando e jogamos o status para o zenity pulsar
	cmdString := fmt.Sprintf("(echo '10'; echo '# Instalando...'; if pkexec %s '%s'; then echo '100'; else echo 'err'; exit 1; fi) | zenity --progress --title='Instalando...' --pulsate --auto-close --no-cancel --width=400", installCmd, filePath)
	
	cmd := exec.Command("bash", "-c", cmdString)
	err := cmd.Run()
	return err == nil
}

func runPkexecBash(bashCmd, title string) bool {
	cmdString := fmt.Sprintf("(echo '10'; echo '# %s'; if pkexec bash -c \"%s\"; then echo '100'; else echo 'err'; exit 1; fi) | zenity --progress --title='%s' --pulsate --auto-close --no-cancel --width=400", title, bashCmd, title)
	cmd := exec.Command("bash", "-c", cmdString)
	err := cmd.Run()
	return err == nil
}

// Wrappers para Zenity
func zenityQuestion(text string) bool {
	err := exec.Command("zenity", "--question", "--text="+text, "--width=400").Run()
	return err == nil
}

func zenityError(text string) {
	exec.Command("zenity", "--error", "--text="+text, "--width=400").Run()
}

func zenityInfo(text string) {
	exec.Command("zenity", "--info", "--text="+text, "--width=350").Run()
}
