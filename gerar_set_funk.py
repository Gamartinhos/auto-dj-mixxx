import subprocess
from pathlib import Path
import json

# Lista de faixas de Funk Consciente para o set de Warm Up
tracks = [
    {"artist": "MC Hariel", "title": "Maçã Verde", "query": "MC Hariel Maçã Verde oficial"},
    {"artist": "MC Lipi", "title": "Anota Ai", "query": "MC Lipi Anota Ai oficial"},
    {"artist": "MC Paulin da Capital", "title": "Mandrake", "query": "MC Paulin da Capital Mandrake oficial"},
    {"artist": "MC Kevin", "title": "Cavalo de Troia", "query": "MC Kevin Cavalo de Troia oficial"},
    {"artist": "MC IG", "title": "3 Dias Virado", "query": "MC IG 3 Dias Virado oficial"}
]

download_dir = Path.home() / "Music" / "AutoDJ_Downloads"
download_dir.mkdir(parents=True, exist_ok=True)

print("Iniciando o garimpo e download das faixas...")
for t in tracks:
    print(f"Baixando: {t['artist']} - {t['title']}")
    cmd = [
        "yt-dlp",
        f"ytsearch1:{t['query']}",
        "--extract-audio",
        "--audio-format", "mp3",
        "--output", f"{download_dir}/{t['artist']} - {t['title']}.%(ext)s",
        "--no-playlist",
        "--match-filter", "duration < 400"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    print("OK Baixado")

# Gerar o plano de transições
transitions = []
for i in range(len(tracks) - 1):
    cur = tracks[i]
    nxt = tracks[i+1]
    
    # Warm up de funk: transições curtas e precisas, muitas vezes usando bass_swap ou hard_cut
    transitions.append({
        "from_artist": cur["artist"],
        "from_title": cur["title"],
        "to_artist": nxt["artist"],
        "to_title": nxt["title"],
        "overlap_beats": 16 if i % 2 == 0 else 32,
        "eq_style": "bass_swap",
        "filter_sweep": True,
        "note": "Transição estilo Funk: Troca rápida de grave no drop (16/32 beats)"
    })

set_data = {
    "name": "Warm Up Funk Consciente",
    "transitions": transitions
}

sets_dir = Path(__file__).parent / "sets"
sets_dir.mkdir(exist_ok=True)
set_file = sets_dir / "active_set.json"

with open(set_file, "w", encoding="utf-8") as f:
    json.dump(set_data, f, indent=2, ensure_ascii=False)

# Criar a playlist .m3u para o usuario arrastar de uma vez
m3u_file = download_dir / "00_WarmUp_Funk_Consciente.m3u"
with open(m3u_file, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for t in tracks:
        # Usa wildcards ou nome exato, mas como o yt-dlp pode mudar caracteres, iteramos os arquivos
        prefix = f"{t['artist']} - "
        for file in download_dir.glob("*.mp3"):
            if file.name.startswith(prefix):
                f.write(f"{file.name}\n")
                break

print(f"\nSet '{set_data['name']}' gerado com sucesso em {set_file}!")
print(f"As músicas e a PLAYLIST (.m3u) foram salvas em: {download_dir}")
