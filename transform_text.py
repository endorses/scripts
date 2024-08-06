#!/usr/bin/env python

import sys
import argparse

NORMAL_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123465789ÜÖÄüöä"
REPLACE_DICT = {
        "b":"𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟔𝟓𝟕𝟖𝟗",
        "i":"𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧0123456789",
        "f":"∀𐐒Ↄ◖ƎℲ⅁HIſ⋊⅂WᴎOԀΌᴚS⊥∩ᴧMX⅄Zɐqɔpǝɟƃɥıɾʞʃɯuodbɹsʇnʌʍxʎz012Ɛᔭ59Ɫ86",
        "bÜ":"𝐔̈","bÖ":"𝐎̈","bÄ":"𝐀̈","bü":"𝐮̈","bö":"𝐨̈","bä":"𝐚̈","iÜ":"𝑈̈",
        "iÖ":"𝑂̈","iÄ":"𝐴̈","iü":"𝑢̈","iö":"𝑜̈","iä":"𝑎̈","fÜ":"∩","fÖ":"O",
        "fÄ":"∀","fü":"n","fö":"o","fä":"ɐ"
        }

def change_text(starttext,change_mode,reverse):
    result = ""
    for letter in starttext:
        position = NORMAL_CHARS.find(letter)
        if position > 61:
            result += REPLACE_DICT[change_mode + letter]
        elif position >= 0:
            result += REPLACE_DICT[change_mode][position]
        else:
            result += letter
    if reverse or change_mode == "f":
        return result[::-1]
    else:
        return result

def main():
    parser = argparse.ArgumentParser(description='Turn text from standard input into bold, italic or upside-down UTF-8')
    parser.add_argument("-b", "--bold", action='store_true', help="turns text into bold UTF-8")
    parser.add_argument("-i", "--italic", action='store_true', help="turns text into italic UTF-8")
    parser.add_argument("-f", "--flip", action='store_true', help="flips text upside-down UTF-8")
    parser.add_argument("-r", "--reverse", action='store_true', help="reverse text")
    args = parser.parse_args()

    modes = []
    if args.bold:
        modes.append("b")
    if args.italic:
        modes.append("i")
    if args.flip:
        modes.append("f")
    if not args.bold and not args.italic and not args.flip:
        modes = ["b","i","f"]

    lines = sys.stdin.readlines()
    result = ""
    for mode in modes:
        for line in lines:
            if result != "":
                result += "\n"
            result += change_text(line.rstrip(),mode,args.reverse)
    sys.stdout.write(result)

if __name__ == "__main__":
    main()
