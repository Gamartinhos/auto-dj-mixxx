"""Gera o mapeamento do Mixxx (XML + JS) a partir de autodj/protocol.py.

Uso:  .venv\\Scripts\\python.exe tools/generate_mapping.py
Saida: mixxx/AutoDJ-Clone.midi.xml  e  mixxx/AutoDJ-Clone-scripts.js
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from autodj import protocol  # noqa: E402

OUT = ROOT / "mixxx"

XML_HEAD = """<?xml version="1.0" encoding="utf-8"?>
<MixxxControllerPreset mixxxVersion="2.5.0" schemaVersion="1">
    <info>
        <name>AutoDJ Clone Bridge</name>
        <author>Auto DJ Clone</author>
        <description>Ponte MIDI entre o cerebro Python (Auto DJ Clone) e o Mixxx. Gerado por tools/generate_mapping.py - nao edite a mao.</description>
        <forums></forums>
    </info>
    <controller id="AutoDJClone">
        <scriptfiles>
            <file filename="AutoDJ-Clone-scripts.js" functionprefix="AutoDJClone"/>
        </scriptfiles>
        <controls>
"""

XML_CONTROL = """            <control>
                <group>[Master]</group>
                <key>AutoDJClone.cmd</key>
                <status>0xB0</status>
                <midino>0x{cc:02X}</midino>
                <description>{name}</description>
                <options>
                    <script-binding/>
                </options>
            </control>
"""

XML_TAIL = """        </controls>
        <outputs/>
    </controller>
</MixxxControllerPreset>
"""

JS_TEMPLATE = r"""/*
 * AutoDJ-Clone-scripts.js  --  GERADO por tools/generate_mapping.py (nao edite a mao)
 *
 * Recebe comandos MIDI (CC, canal 1) do cerebro Python e aplica nos controles do Mixxx.
 * Publica o estado dos decks via SysEx  F0 7D <json ascii> F7  a cada STATE_INTERVAL_MS.
 */
var AutoDJClone = {};

AutoDJClone.STATE_INTERVAL_MS = 250;
AutoDJClone.table = __TABLE__;

AutoDJClone.init = function (id, debugging) {
    AutoDJClone.id = id;
    AutoDJClone.timer = engine.beginTimer(AutoDJClone.STATE_INTERVAL_MS, AutoDJClone.sendState);
    print("[AutoDJClone] init ok - " + Object.keys(AutoDJClone.table).length + " comandos");
    AutoDJClone.sendState();
};

AutoDJClone.shutdown = function () {
    if (AutoDJClone.timer) {
        engine.stopTimer(AutoDJClone.timer);
        AutoDJClone.timer = 0;
    }
    print("[AutoDJClone] shutdown");
};

// Handler unico: todos os CCs do mapeamento chamam esta funcao.
AutoDJClone.cmd = function (channel, control, value, status, group) {
    var e = AutoDJClone.table[control];
    if (!e) { return; }
    if (e.k === "") {              // request_state
        AutoDJClone.sendState();
        return;
    }
    var frac = value / 127.0;
    var mid = (value === 64);      // 64 vira exatamente o centro (EQ neutro, crossfader 0)
    switch (e.t) {
    case "bool":
        engine.setValue(e.g, e.k, value >= 64 ? 1 : 0);
        break;
    case "trigger":
        if (value > 0) { engine.setValue(e.g, e.k, 1); }
        break;
    case "param":
        engine.setParameter(e.g, e.k, mid ? 0.5 : frac);
        break;
    case "range":
        engine.setValue(e.g, e.k, mid ? (e.lo + e.hi) / 2 : e.lo + (e.hi - e.lo) * frac);
        break;
    case "int":
        engine.setValue(e.g, e.k, value);
        break;
    case "offset64":
        engine.setValue(e.g, e.k, value - 64);
        break;
    }
};

AutoDJClone.r3 = function (x) {
    if (typeof x !== "number" || isNaN(x)) { return 0; }
    return Math.round(x * 1000) / 1000;
};

AutoDJClone.deckState = function (n) {
    var g = "[Channel" + n + "]";
    return {
        pl: engine.getValue(g, "play") ? 1 : 0,
        pos: AutoDJClone.r3(engine.getValue(g, "playposition")),
        dur: AutoDJClone.r3(engine.getValue(g, "duration")),
        bpm: AutoDJClone.r3(engine.getValue(g, "bpm")),
        fb: AutoDJClone.r3(engine.getValue(g, "file_bpm")),
        ld: engine.getValue(g, "track_loaded") ? 1 : 0,
        vol: AutoDJClone.r3(engine.getValue(g, "volume")),
        sy: engine.getValue(g, "sync_enabled") ? 1 : 0
    };
};

AutoDJClone.sendState = function () {
    var s = {
        v: 1,
        adj: engine.getValue("[AutoDJ]", "enabled") ? 1 : 0,
        tr: AutoDJClone.r3(engine.getValue("[AutoDJ]", "transition")),
        cf: AutoDJClone.r3(engine.getValue("[Master]", "crossfader")),
        d: [AutoDJClone.deckState(1), AutoDJClone.deckState(2)]
    };
    var json = JSON.stringify(s);
    var bytes = [0xF0, 0x7D];
    for (var i = 0; i < json.length; i++) {
        bytes.push(json.charCodeAt(i) & 0x7F);
    }
    bytes.push(0xF7);
    midi.sendSysexMsg(bytes, bytes.length);
};
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)

    xml = [XML_HEAD]
    for c in protocol.COMMANDS:
        xml.append(XML_CONTROL.format(cc=c.cc, name=c.name))
    xml.append(XML_TAIL)
    (OUT / "AutoDJ-Clone.midi.xml").write_text("".join(xml), encoding="utf-8", newline="\n")

    table = {
        str(c.cc): {"n": c.name, "g": c.group, "k": c.key, "t": c.kind, "lo": c.lo, "hi": c.hi}
        for c in protocol.COMMANDS
    }
    # chaves do objeto JS como numeros (control chega como inteiro)
    table_js = json.dumps(table, indent=4)
    js = JS_TEMPLATE.replace("__TABLE__", table_js)
    (OUT / "AutoDJ-Clone-scripts.js").write_text(js, encoding="utf-8", newline="\n")

    print(f"OK: {len(protocol.COMMANDS)} comandos -> {OUT}")


if __name__ == "__main__":
    main()
