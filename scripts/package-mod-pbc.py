"""Package the pinned Playerbot Characters runtime for a CoA repack."""
import argparse
from pathlib import Path
import re
import shutil


def package(module, out):
    assets = out / "Extras/PlayerbotCharacters"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copytree(module / "prompts", assets / "prompts", dirs_exist_ok=True)
    shutil.copytree(module / "frontend/dist", assets / "dashboard", dirs_exist_ok=True)
    shutil.copy2(module / "characters/Example.card.txt", assets / "Example.card.txt")
    examples = assets / "connection-examples"
    examples.mkdir(exist_ok=True)
    templates = sorted((module / "connections").glob("*.jsonc.example"))
    if not templates:
        raise RuntimeError("The pinned mod-pbc source has no connection examples")
    for template in templates:
        shutil.copy2(template, examples / template.name)

    cards = assets / "cards"
    cards.mkdir(exist_ok=True)
    (cards / "README.txt").write_text(
        "Save your character cards here as CharacterName.card.txt. See ../Example.card.txt for an example.\n",
        encoding="utf-8",
    )
    (assets / "README.txt").write_text(
        "Playerbot Characters\n\n"
        "In CoA Server Manager, open Modules and the Playerbot Characters settings. Choose a provider,\n"
        "enter your model and API key if needed, then save the connection. Enable the module and restart.\n"
        "Run .chars connection-test in game with a GM account, then summon a companion and whisper it.\n\n"
        "For manual setup, copy an example from connection-examples to my-connection.jsonc in this folder.\n\n"
        "Model setup guide\nhttps://github.com/deseven/mod-pbc/blob/main/docs/CONNECTIONS.md\n",
        encoding="utf-8",
    )

    template = module / "conf/playerbots_characters.conf.dist"
    config = template.read_text(encoding="utf-8")
    relative = "../Extras/PlayerbotCharacters"  # worldserver runs from Core/.
    defaults = {
        "PBC.Enable": "0",
        "PBC.DefaultConnection": f'"{relative}/my-connection.jsonc"',
        "PBC.PromptsPath": f'"{relative}/prompts"',
        "PBC.CharacterCardsPath": f'"{relative}/cards"',
        "PBC.HttpServerFrontendPath": f'"{relative}/dashboard"',
    }
    for key, value in defaults.items():
        config, count = re.subn(rf"(?m)^{re.escape(key)}[ \t]*=.*$", f"{key} = {value}", config)
        if count != 1:
            raise RuntimeError(f"Expected one mod-pbc config key: {key}")
    config_dir = out / "Core/configs/modules"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / template.name).write_text(config, encoding="utf-8", newline="\n")

    licenses = out / "Licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(module / "LICENSE", licenses / "mod-pbc-LICENSE.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    package(args.module, args.out)
