# CappinCrunch

GUI helper for the `crunch` wordlist generator, plus a built-in "smart" generator for prefix/suffix patterns around custom keywords. It offers profiles, previews, estimates, and optional post-processing.

![CappinCrunch GUI](https://github.com/sweetenloe/CappinCrunch/blob/main/screenshot.png)

## What it uses
- Python 3
- Tkinter (GUI)
- `crunch` (optional; required for non-smart generation)

## Features
- Charset mode: generate wordlists with `crunch`
- Custom dictionary mode: permute keywords with `crunch -p`
- Smart mode: generates `prefix + keyword + suffix` using a selected charset
- Combine keywords (concatenation with `_` and `-` variants)
- Output preview + estimated size
- Profiles saved to `~/.cappincrunch_profiles.json`
- Optional post command with `{wordlist}` placeholder

## Dependencies
Required:
- Python 3
- Tkinter

Optional (for crunch-based generation):
- `crunch`

## Install dependencies (Ubuntu/Debian)
```bash
sudo apt-get update && sudo apt-get install -y crunch python3-tk
```

## Run
```bash
python3 CappinCrunch.py
```

## Notes
- If no output file is chosen, it defaults to `namethisoutput.txt` in the current working directory.
- Smart mode writes the output directly (no `crunch` needed).
- The program will warn and offer a cap when smart mode might generate a very large list.

## Attribution
Some of the more elaborate or time-consuming features were implemented with the help of Codex.
