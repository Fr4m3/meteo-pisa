#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera verifica.html dal report storico (verifica_storico.json)."""
import json
from datetime import datetime

def js(o):
    return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

def main():
    storico = json.load(open("verifica_storico.json"))
    tpl = open("verifica.template.html", encoding="utf-8").read()
    out = tpl.replace("__VERIFICA_JSON__", js(storico))
    open("verifica.html", "w", encoding="utf-8").write(out)
    print(f"verifica.html scritto ({len(out)} byte) — {len(storico['runs'])} corse nel report.")

if __name__ == "__main__":
    main()