/*
 * AutoDJ-Clone-scripts.js  --  GERADO por tools/generate_mapping.py (nao edite a mao)
 *
 * Recebe comandos MIDI (CC, canal 1) do cerebro Python e aplica nos controles do Mixxx.
 * Publica o estado dos decks via SysEx  F0 7D <json ascii> F7  a cada STATE_INTERVAL_MS.
 */
var AutoDJClone = {};

AutoDJClone.STATE_INTERVAL_MS = 250;
AutoDJClone.table = {
    "16": {
        "n": "d1_play",
        "g": "[Channel1]",
        "k": "play",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "17": {
        "n": "d1_sync",
        "g": "[Channel1]",
        "k": "sync_enabled",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "18": {
        "n": "d1_load",
        "g": "[Channel1]",
        "k": "LoadSelectedTrack",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "19": {
        "n": "d1_eq_low",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "parameter1",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "20": {
        "n": "d1_eq_mid",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "parameter2",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "21": {
        "n": "d1_eq_high",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "parameter3",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "22": {
        "n": "d1_kill_low",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "button_parameter1",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "23": {
        "n": "d1_kill_mid",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "button_parameter2",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "24": {
        "n": "d1_kill_high",
        "g": "[EqualizerRack1_[Channel1]_Effect1]",
        "k": "button_parameter3",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "25": {
        "n": "d1_filter",
        "g": "[QuickEffectRack1_[Channel1]]",
        "k": "super1",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "26": {
        "n": "d1_volume",
        "g": "[Channel1]",
        "k": "volume",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "27": {
        "n": "d1_cue",
        "g": "[Channel1]",
        "k": "cue_default",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "28": {
        "n": "d1_pfl",
        "g": "[Channel1]",
        "k": "pfl",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "29": {
        "n": "d1_eject",
        "g": "[Channel1]",
        "k": "eject",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "30": {
        "n": "d1_load_play",
        "g": "[Channel1]",
        "k": "LoadSelectedTrackAndPlay",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "48": {
        "n": "d2_play",
        "g": "[Channel2]",
        "k": "play",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "49": {
        "n": "d2_sync",
        "g": "[Channel2]",
        "k": "sync_enabled",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "50": {
        "n": "d2_load",
        "g": "[Channel2]",
        "k": "LoadSelectedTrack",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "51": {
        "n": "d2_eq_low",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "parameter1",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "52": {
        "n": "d2_eq_mid",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "parameter2",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "53": {
        "n": "d2_eq_high",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "parameter3",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "54": {
        "n": "d2_kill_low",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "button_parameter1",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "55": {
        "n": "d2_kill_mid",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "button_parameter2",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "56": {
        "n": "d2_kill_high",
        "g": "[EqualizerRack1_[Channel2]_Effect1]",
        "k": "button_parameter3",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "57": {
        "n": "d2_filter",
        "g": "[QuickEffectRack1_[Channel2]]",
        "k": "super1",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "58": {
        "n": "d2_volume",
        "g": "[Channel2]",
        "k": "volume",
        "t": "param",
        "lo": 0.0,
        "hi": 1.0
    },
    "59": {
        "n": "d2_cue",
        "g": "[Channel2]",
        "k": "cue_default",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "60": {
        "n": "d2_pfl",
        "g": "[Channel2]",
        "k": "pfl",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "61": {
        "n": "d2_eject",
        "g": "[Channel2]",
        "k": "eject",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "62": {
        "n": "d2_load_play",
        "g": "[Channel2]",
        "k": "LoadSelectedTrackAndPlay",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "96": {
        "n": "crossfader",
        "g": "[Master]",
        "k": "crossfader",
        "t": "range",
        "lo": -1.0,
        "hi": 1.0
    },
    "97": {
        "n": "autodj_enable",
        "g": "[AutoDJ]",
        "k": "enabled",
        "t": "bool",
        "lo": 0.0,
        "hi": 1.0
    },
    "98": {
        "n": "autodj_fade_now",
        "g": "[AutoDJ]",
        "k": "fade_now",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "99": {
        "n": "autodj_skip_next",
        "g": "[AutoDJ]",
        "k": "skip_next",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "100": {
        "n": "autodj_shuffle",
        "g": "[AutoDJ]",
        "k": "shuffle_playlist",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "101": {
        "n": "autodj_add_random",
        "g": "[AutoDJ]",
        "k": "add_random_track",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    },
    "102": {
        "n": "autodj_transition",
        "g": "[AutoDJ]",
        "k": "transition",
        "t": "offset64",
        "lo": 0.0,
        "hi": 1.0
    },
    "126": {
        "n": "request_state",
        "g": "[Master]",
        "k": "",
        "t": "trigger",
        "lo": 0.0,
        "hi": 1.0
    }
};

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
