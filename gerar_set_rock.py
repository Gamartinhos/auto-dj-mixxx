"""Gerador de Set e Playlist: Show de Rock 1 Hora (Especial Mosh Pit)

Execução:
    .venv\\Scripts\\python.exe gerar_set_rock.py              # Garimpa, baixa faixas e gera set
    .venv\\Scripts\\python.exe gerar_set_rock.py --no-download  # Apenas gera JSON do set e playlist .m3u
"""
import argparse
import json
import subprocess
from pathlib import Path

# Lista curada de 17 pedradas para 1 hora ininterrupta de Mosh Pit
TRACKS = [
    {
        "artist": "System of a Down",
        "title": "Chop Suey!",
        "query": "System of a Down Chop Suey official audio",
        "bpm": 127,
        "note": "Abertura explosiva que acorda a plateia e abre a roda no primeiro 'Wake up!'"
    },
    {
        "artist": "Rage Against the Machine",
        "title": "Bulls on Parade",
        "query": "Rage Against the Machine Bulls on Parade official audio",
        "bpm": 83,
        "note": "Riff com groove pesado para pular e bater cabeça"
    },
    {
        "artist": "Limp Bizkit",
        "title": "Break Stuff",
        "query": "Limp Bizkit Break Stuff official audio",
        "bpm": 110,
        "note": "O hino supremo de mosh pit ('Give me something to break!')"
    },
    {
        "artist": "Slipknot",
        "title": "Duality",
        "query": "Slipknot Duality official audio",
        "bpm": 144,
        "note": "Explosão de percussão, refrão agressivo cantado em coro"
    },
    {
        "artist": "Linkin Park",
        "title": "Faint",
        "query": "Linkin Park Faint official audio",
        "bpm": 135,
        "note": "Velocidade rápida e os berros rasgados de Chester Bennington"
    },
    {
        "artist": "Papa Roach",
        "title": "Last Resort",
        "query": "Papa Roach Last Resort official audio",
        "bpm": 91,
        "note": "Clássico dos anos 2000 que incendeia a roda"
    },
    {
        "artist": "Deftones",
        "title": "My Own Summer (Shove It)",
        "query": "Deftones My Own Summer official audio",
        "bpm": 139,
        "note": "Afinação pesada em Drop D, groove visceral"
    },
    {
        "artist": "Drowning Pool",
        "title": "Bodies",
        "query": "Drowning Pool Bodies official audio",
        "bpm": 125,
        "note": "O famoso 'Let the bodies hit the floor' — contagem para colisão frontal"
    },
    {
        "artist": "Disturbed",
        "title": "Down with the Sickness",
        "query": "Disturbed Down with the Sickness official audio",
        "bpm": 90,
        "note": "O icônico 'OOH-WAH-AH-AH-AH' e breakdown pesado"
    },
    {
        "artist": "Pantera",
        "title": "Walk",
        "query": "Pantera Walk official audio",
        "bpm": 118,
        "note": "O riff mais pesado do Groove Metal, hino de Circle Pit ('RE-SPECT, WALK!')"
    },
    {
        "artist": "Sepultura",
        "title": "Roots Bloody Roots",
        "query": "Sepultura Roots Bloody Roots official audio",
        "bpm": 144,
        "note": "Pancada brasileira com percussão tribal e afinação gravíssima"
    },
    {
        "artist": "Metallica",
        "title": "Master of Puppets",
        "query": "Metallica Master of Puppets official audio",
        "bpm": 212,
        "note": "Aceleração insana de Thrash Metal para ferver a roda"
    },
    {
        "artist": "Avenged Sevenfold",
        "title": "Hail to the King",
        "query": "Avenged Sevenfold Hail to the King official audio",
        "bpm": 118,
        "note": "Marcha cadenciada de arena com guitarras gêmeas"
    },
    {
        "artist": "Bring Me The Horizon",
        "title": "Can You Feel My Heart",
        "query": "Bring Me The Horizon Can You Feel My Heart official audio",
        "bpm": 128,
        "note": "Metalcore moderno com parede sonora gigante"
    },
    {
        "artist": "Foo Fighters",
        "title": "All My Life",
        "query": "Foo Fighters All My Life official audio",
        "bpm": 166,
        "note": "Riff em alta velocidade com pegada punk/hard rock"
    },
    {
        "artist": "The Offspring",
        "title": "The Kids Aren't Alright",
        "query": "The Offspring The Kids Arent Alright official audio",
        "bpm": 148,
        "note": "Sprint de Skate Punk rápido antes do grand finale"
    },
    {
        "artist": "Rage Against the Machine",
        "title": "Killing in the Name",
        "query": "Rage Against the Machine Killing in the Name official audio",
        "bpm": 89,
        "note": "Clímax do show: o crescendo de 'Fuck you I won't do what you tell me!'"
    }
]


def download_tracks(download_dir: Path):
    print(f"\n[1/3] Iniciando garimpo e download em: {download_dir}")
    download_dir.mkdir(parents=True, exist_ok=True)

    for i, t in enumerate(TRACKS, 1):
        prefix = f"{t['artist']} - {t['title']}"
        clean_title = t["title"].split("(")[0].strip(" !")
        existing = [f for f in download_dir.glob(f"{t['artist']} - *.mp3") if clean_title.lower() in f.name.lower()]
        if existing:
            print(f"  [{i}/{len(TRACKS)}] Já existe: {existing[0].name}")
            continue

        print(f"  [{i}/{len(TRACKS)}] Baixando: {t['artist']} - {t['title']}...")
        cmd = [
            "yt-dlp",
            f"ytsearch1:{t['query']}",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", f"{download_dir}/{prefix}.%(ext)s",
            "--no-playlist",
            "--match-filter", "duration < 550"
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            print(f"         OK: {t['artist']} - {t['title']}")
        else:
            print(f"         AVISO: Falha ao baixar '{t['title']}': {res.stderr[:100]}")


def build_transitions():
    """Gera o plano coreografado com cortes secos, stutters, vinyl brakes e trocas de breakdown."""
    plan_cues = [
        {"overlap": 8, "style": "stutter_drop", "note": "Gracinha Morello: Gaguejo rítmico no final de Chop Suey e corte seco no cowbell/bateria de Bulls on Parade"},
        {"overlap": 16, "style": "bass_swap", "note": "Troca rápida de bumbo na batida seca de Break Stuff mantendo o groove da pista"},
        {"overlap": 12, "style": "breakdown_swap", "note": "Breakdown Drop: Mantém o peso de Break Stuff até o último instante e explode no prato/percussão de Duality"},
        {"overlap": 8, "style": "hard_cut", "note": "Corte seco e direto nos violinos/riff rápido de Faint"},
        {"overlap": 10, "style": "brake_cut", "note": "Vinyl Brake: Freada rápida no último grito do Chester e entrada crua no riff icônico de Last Resort"},
        {"overlap": 16, "style": "breakdown_swap", "note": "Troca de grave no breakdown para o peso arrastado em Drop D de My Own Summer"},
        {"overlap": 12, "style": "wash_out", "note": "Washout / Silêncio total: Filtro sobe e corta a zero para a contagem '1, nothing wrong with me...'"},
        {"overlap": 8, "style": "breakdown_swap", "note": "Breakdown Drop: Bate seco direto no 'OOH-WAH-AH-AH-AH' da intro de Down with the Sickness"},
        {"overlap": 8, "style": "hard_cut", "note": "Corte seco no primeiro acorde arrastado de Dimebag Darrell para abrir o Circle Pit"},
        {"overlap": 8, "style": "brake_cut", "note": "Brake rápido e explosão imediata no berro 'Roots, Bloody Roots!'"},
        {"overlap": 8, "style": "stutter_drop", "note": "Stutter / Gaguejo acelerando o bumbo antes de soltar a palhetada veloz de Master of Puppets"},
        {"overlap": 16, "style": "wash_out", "note": "Washout abrindo espaço para a marcha cadenciada de arena com guitarras gêmeas de Hail to the King"},
        {"overlap": 12, "style": "breakdown_swap", "note": "Troca no drop do sintetizador com parede de som de metalcore moderno de Can You Feel My Heart"},
        {"overlap": 8, "style": "hard_cut", "note": "Corte instantâneo para o ataque rápido de bateria de Dave Grohl em All My Life"},
        {"overlap": 8, "style": "brake_cut", "note": "Freada rápida de vinil e disparo no skate punk em alta velocidade de The Kids Aren't Alright"},
        {"overlap": 12, "style": "stutter_drop", "note": "Gracinha Morello: Stutter rítmico no prato de condução e drop no baixo icônico de Killing in the Name para a apoteose final"},
    ]

    transitions = []
    for i in range(len(TRACKS) - 1):
        cur = TRACKS[i]
        nxt = TRACKS[i + 1]
        cue = plan_cues[i] if i < len(plan_cues) else {"overlap": 8, "style": "hard_cut", "note": nxt["note"]}

        transitions.append({
            "from_artist": cur["artist"],
            "from_title": cur["title"],
            "to_artist": nxt["artist"],
            "to_title": nxt["title"],
            "overlap_beats": cue["overlap"],
            "eq_style": cue["style"],
            "filter_sweep": cue["style"] == "wash_out",
            "note": cue["note"]
        })
    return transitions


def save_set_and_playlist(download_dir: Path):
    print("\n[2/3] Gerando active_set.json e backup...")
    transitions = build_transitions()
    set_data = {
        "name": "Show Rock 1 Hora - Mosh Pit Especial",
        "description": "Set de 1 hora com 17 faixas de Nu Metal, Hard Rock, Thrash e Punk focado em manter a roda de mosh no pico.",
        "transitions": transitions
    }

    sets_dir = Path(__file__).parent / "sets"
    sets_dir.mkdir(exist_ok=True)
    
    # Salva como active_set.json (o cérebro do Auto DJ lê este arquivo automaticamente)
    active_file = sets_dir / "active_set.json"
    with open(active_file, "w", encoding="utf-8") as f:
        json.dump(set_data, f, indent=2, ensure_ascii=False)
    print(f"  OK: {active_file}")

    # Salva também um backup com nome descritivo
    backup_file = sets_dir / "set_rock_mosh_1hora.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(set_data, f, indent=2, ensure_ascii=False)
    print(f"  OK: {backup_file}")

    print("\n[3/3] Criando arquivos de Playlist (.m3u)...")
    m3u_lines = ["#EXTM3U\n"]
    for t in TRACKS:
        clean_title = t["title"].split("(")[0].strip(" !")
        matched = False
        if download_dir.exists():
            for file in download_dir.glob("*.mp3"):
                if file.name.lower().startswith(f"{t['artist'].lower()} -") and clean_title.lower() in file.name.lower():
                    m3u_lines.append(f"{file.name}\n")
                    matched = True
                    break
        if not matched:
            m3u_lines.append(f"{t['artist']} - {t['title']}.mp3\n")

    m3u_path_music = download_dir / "00_Show_Rock_Mosh_1Hora.m3u"
    m3u_path_sets = sets_dir / "00_Show_Rock_Mosh_1Hora.m3u"

    with open(m3u_path_music, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    with open(m3u_path_sets, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)

    print(f"  OK: {m3u_path_music}")
    print(f"  OK: {m3u_path_sets}")

    print("\n" + "=" * 60)
    print(f"SET '{set_data['name']}' PRONTO!")
    print(f"Total de Faixas: {len(TRACKS)} músicas (~60-64 minutos)")
    print(f"Transições Programadas: {len(transitions)} cortes otimizados para mosh")
    print(f"Perfil recomendado no painel web: 'Rock Mosh Pit' (energia 95-100)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Gerador do Set de Rock 1 Hora - Mosh Pit")
    parser.add_argument("--no-download", action="store_true", help="Gera apenas JSON e .m3u sem baixar arquivos")
    args = parser.parse_args()

    download_dir = Path.home() / "Music" / "AutoDJ_Downloads"
    if not args.no_download:
        download_tracks(download_dir)
    else:
        print("\nModo --no-download: pulando etapa de download.")

    save_set_and_playlist(download_dir)


if __name__ == "__main__":
    main()
