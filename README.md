Tac Writer
Tac Writer é um aplicativo para Linux desenvolvido em Python e GTK 3 que facilita a escrita de textos acadêmicos utilizando a Técnica da Argumentação Continuada (TAC), criada por Narayan Silva. O aplicativo oferece uma interface intuitiva para organizar parágrafos acadêmicos de acordo com a metodologia TAC, com recursos de formatação e exportação.

https://imgur.com/a/6kiAHgQ

Recursos Principais
🧩 Estrutura baseada na Técnica TAC:

Tópico Frasal/Título do parágrafo

Argumentação

Argumentação com citação

Conclusão

📝 Editor avançado:

Formatação personalizada (fonte, tamanho, espaçamento, recuos)

Visualização em tempo real

💾 Gerenciamento de projetos:

Crie e salve múltiplos projetos

Acesso rápido aos trabalhos anteriores

📤 Exportação flexível:

Formato ODT (LibreOffice)

HTML

TXT simples

🌍 Suporte a internacionalização:

Traduções via gettext

Atualmente disponível em Português do Brasil

Técnica TAC (Argumentação Continuada)
A Técnica da Argumentação Continuada é uma metodologia desenvolvida por Narayan Silva para organização de textos acadêmicos complexos. Ela estrutura o texto em parágrafos que dialogam entre si:

Tópico frasal: Frase inicial que sintetiza o tema do parágrafo

Argumentação: Desenvolvimento do tema

Argumentação com citação: Suporte à argumentação com referências externas

Conclusão: Fechamento da ideia apresentada

Instalação
Pré-requisitos
Python 3.11+

GTK 3

GtkSourceView 3

Pacotes Python: PyGObject, odfpy

bash
# No BigLinux/Manjaro
sudo pacman -S python-gobject python-odfpy gtksourceview3
Executando o aplicativo
bash
git clone https://github.com/seu-usuario/tac-writer.git
cd tac-writer
python3 tac.py
Como Usar
Clique em "COMEÇAR A ESCREVER"

Selecione o tipo de parágrafo que deseja criar:

Tópico Frasal

Argumentação

Argumentação com citação

Conclusão

Escreva seu conteúdo

Formate o texto conforme necessário

Salve seu projeto para continuar depois

Exporte para ODT quando finalizado

Capturas de Tela
Menu Principal	Editor	Formatação
https://screenshots/main-menu.png	https://screenshots/editor.png	https://screenshots/formatting.png
Estrutura do Projeto
text
tac-writer/
├── data/              # Armazenamento de projetos
├── po/                # Arquivos de tradução
├── src/               # Código fonte
│   ├── application.py # Aplicação principal
│   ├── config.py      # Configurações
│   ├── editor.py      # Componente editor
│   ├── export.py      # Exportação de documentos
│   ├── main.py        # Ponto de entrada
│   ├── paragraph.py   # Editor de parágrafos
│   ├── project.py     # Gerenciamento de projetos
│   └── window.py      # Janela principal
├── tac.py             # Script de execução
└── README.md          # Este arquivo
Contribuição
Contribuições são bem-vindas! Por favor, abra uma issue para discutir mudanças significativas antes de enviar um pull request.

Licença
Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.

