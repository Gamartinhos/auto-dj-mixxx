# 🎧 Auto DJ Clone (Mixxx + Gemini AI)

Sistema inteligente de **Auto DJ** integrado ao [Mixxx](https://mixxx.org/), utilizando IA generativa (**Google Gemini**) para tomadas de decisão musicais dinâmicas, controle de transições e leitura de energia da pista em tempo real.

---

## ⚡ Principais Recursos

- **Inteligência Musical via Gemini**: Planejamento dinâmico de transições (fade, corte no drop, swap de graves/EQ, filtros) e seleção de faixas baseada em harmonia (Camelot / Key), BPM e energia.
- **Ponte MIDI Bidirecional**: Comunicação com o Mixxx via porta MIDI virtual (`loopMIDI`) e scripts MIDI em JavaScript com troca de estado por mensagens SysEx.
- **Resiliência ("A festa nunca para")**: Se a IA demorar ou perder conexão, o sistema aciona automaticamente heurísticas baseadas no perfil musical ativo.
- **Painel Web em Tempo Real**: Interface moderna construída com FastAPI e WebSockets para monitorar decks, status da mixagem e parâmetros ao vivo.
- **Modo Simulado (`--sim`)**: Permite testar todo o ecossistema e algoritmos sem precisar abrir o Mixxx ou configurar hardware de áudio.
- **Geradores de Set & Perfis**: Scripts utilitários para gerar sets de diferentes gêneros e vibes (Rock, Funk, etc.).

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Python 3.10 ou superior
- [Mixxx DJ Software](https://mixxx.org/) (opcional se for rodar em modo simulado)
- [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) (para ponte MIDI no Windows)

### 2. Instalação

Clone o repositório e crie o ambiente virtual:

```bash
git clone https://github.com/Gamartinhos/auto-dj-mixxx.git
cd auto-dj-mixxx

python -m venv .venv
# No Windows PowerShell:
.venv\Scripts\Activate.ps1
# No Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuração de Variáveis de Ambiente

Copie o arquivo de exemplo `.env.example` para `.env` e configure sua chave da API do Gemini:

```bash
cp .env.example .env
```

Edite o `.env`:
```env
GEMINI_API_KEY=sua_chave_gemini_aqui
AUTODJ_AI_TIMEOUT=300
AUTODJ_GEMINI_MODEL=gemini-3.8-flash
```

### 4. Executando o Projeto

#### Modo Simulado (sem Mixxx)
Ideal para desenvolvimento e testes rápidos de lógica e interface:
```bash
python main.py --sim
```

#### Modo Real (conectado ao Mixxx)
1. Crie uma porta virtual no loopMIDI com nome `AutoDJ`.
2. No Mixxx, carregue o mapeamento MIDI localizado na pasta `mixxx/`.
3. Inicie a aplicação:
```bash
python main.py
```

#### Acesso na Rede Local (LAN / Celular)
```bash
python main.py --lan
```
Acesse a interface web através do endereço exibido no terminal (ex: `http://localhost:8000/`).

---

## 📁 Estrutura do Projeto

```
├── autodj/             # Núcleo da aplicação
│   ├── ai.py           # Agente IA (Gemini) e ferramentas
│   ├── brain.py        # Orquestrador do estado e tomadas de decisão
│   ├── config.py       # Configurações e variáveis de ambiente
│   ├── library.py      # Conexão com a biblioteca SQLite do Mixxx
│   ├── mixxx_link.py   # Ponte MIDI (mido) com o Mixxx
│   ├── profiles.py     # Gerenciamento de perfis e estilos musicais
│   ├── protocol.py     # Protocolo de comandos e codificação SysEx
│   ├── selection.py    # Algoritmos de seleção de faixas e harmonia
│   ├── server.py       # API FastAPI e endpoints WebSocket
│   ├── sim.py          # Simulador de decks para testes offline
│   └── transitions.py  # Automação de curvas de volume, EQ e crossfader
├── mixxx/              # Mapeamentos MIDI (.midi.xml e scripts .js)
├── sets/               # Playlists e sets gerados (.json, .m3u)
├── tools/              # Ferramentas auxiliares
├── web/                # Interface frontend (HTML/CSS/JS)
├── main.py             # Ponto de entrada do sistema
└── profiles.json       # Configuração de perfis musicais
```

---

## 🛡️ Licença
Distribuído sob a licença MIT. Consulte `LICENSE` para mais informações.
