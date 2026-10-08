#!/usr/bin/env python3
"""Transform stdin while preserving whitespace and line endings."""

import argparse
import re
import sys
import unicodedata

NORMAL_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
STYLES = {
    "b": "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
    "i": "𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧0123456789",
    "f": "∀𐐒Ↄ◖ƎℲ⅁HIſ⋊⅂WᴎOԀΌᴚS⊥∩ᴧMX⅄Zɐqɔpǝɟƃɥıɾʞʃɯuodbɹsʇnʌʍxʎz012Ɛᔭ59Ɫ86",
}
UMLAUTS = {
    "b": ("𝐔̈", "𝐎̈", "𝐀̈", "𝐮̈", "𝐨̈", "𝐚̈"),
    "i": ("𝑈̈", "𝑂̈", "𝐴̈", "𝑢̈", "𝑜̈", "𝑎̈"),
    "f": ("∩", "O", "∀", "n", "o", "ɐ"),
}
TRANSLATIONS = {
    mode: dict(zip(NORMAL_CHARS + "ÜÖÄüöä", list(style) + list(UMLAUTS[mode])))
    for mode, style in STYLES.items()
}


def character_groups(text):
    """Keep combining marks with their base; this is not full grapheme segmentation."""
    groups = []
    for character in text:
        if groups and unicodedata.category(character).startswith("M"):
            groups[-1] += character
        else:
            groups.append(character)
    return groups


def change_text(starttext, change_mode=None, reverse=False):
    """Transform a single line, leaving unrecognized characters unchanged."""
    groups = character_groups(starttext)
    if change_mode is not None:
        translation = TRANSLATIONS[change_mode]
        transformed = []
        for group in groups:
            # Recognize decomposed umlauts without normalizing unrelated input.
            umlaut = unicodedata.normalize("NFC", group)
            if umlaut in "ÜÖÄüöä":
                transformed.append(translation[umlaut])
            else:
                transformed.append("".join(translation.get(c, c) for c in group))
        groups = transformed
    if reverse or change_mode == "f":
        groups.reverse()
    return "".join(groups)


def transform_lines(text, mode=None, reverse=False):
    """Transform each line independently, retaining its exact CR/LF separator."""
    parts = re.split(r"(\r\n|\r|\n)", text)
    for index in range(0, len(parts), 2):
        parts[index] = change_text(parts[index], mode, reverse)
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Turn stdin into bold, italic or upside-down Unicode text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""With no flags, output all three styles. Style flags can be combined.
Reverse alone reverses plain text; flip always reverses each line once.
Combining accents stay with their base letter during reversal; complex
emoji sequences are not treated as single characters.

Examples:
  printf 'Hello world\\n' | transform_text.py --bold
  printf 'Hello' | transform_text.py --bold --italic
  printf 'Hello' | transform_text.py --reverse
  printf 'Hello' | transform_text.py --flip""",
    )
    parser.add_argument("-b", "--bold", action="store_true", help="output bold text")
    parser.add_argument(
        "-i", "--italic", action="store_true", help="output italic text"
    )
    parser.add_argument(
        "-f", "--flip", action="store_true", help="output upside-down text"
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="reverse each line, preserving accents",
    )
    args = parser.parse_args()
    modes = [
        mode
        for mode, enabled in (("b", args.bold), ("i", args.italic), ("f", args.flip))
        if enabled
    ]
    if not modes:
        modes = [None] if args.reverse else ["b", "i", "f"]

    # Disable universal-newline conversion so CRLF and CR input survive intact.
    sys.stdin.reconfigure(newline="")
    sys.stdout.reconfigure(newline="")
    text = sys.stdin.read()
    separator = "" if not text or text.endswith(("\r", "\n")) else "\n"
    sys.stdout.write(
        separator.join(transform_lines(text, mode, args.reverse) for mode in modes)
    )


if __name__ == "__main__":
    main()
