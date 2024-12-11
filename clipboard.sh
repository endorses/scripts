#!/usr/bin/bash

strarr="good morning
goodbye"


clip=$(printf "$strarr" | dmenu -l 20 -c -p Clipboard)

if [ ! -z "$clip" ]; then
    case $clip in
        "good morning") str="good morning :wave:";;
        "goodbye") str="gone for today :wave:";;
    esac
fi

printf "$str" | xclip -i -selection c 
