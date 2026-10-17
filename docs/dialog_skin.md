# IE-style dialogue window (Temple+ dialog skins)

`proto/ie_dialog_skin.py` rebuilds the Infinity Engine conversation window from the player's own IWD install
and writes it as a *dialog skin* that a Temple+ build with the `feature/ie-dialog-skin` branch can show instead
of the stock ToEE dialogue window. Like the rest of ie2toee, **no IE art ships**: the art, fonts and layout are
extracted on the player's machine. Temple+ only ships the code that draws a skin.

## Usage

    python3 proto/ie_dialog_skin.py <IWD install> <output dir> [--skin auto|all|iwdee|iwd]
        [--default SKIN] [--dialog ID[:SKIN]]... [--portrait ID:CRE]... [--lang en_US]

* `--skin auto` (default) exports the skin matching the install: `iwdee` for Enhanced Edition, `iwd` for
  classic. `all` exports every skin the install can provide (an EE install can also provide the classic
  layout, from its `GUIW.CHU`).
* `--default` picks the skin used for every dialogue (omit it to keep the stock window except for the
  dialogues named with `--dialog`).
* `--dialog 993:iwdee` uses a skin for one ToEE dialogue file id only (e.g. the converted IWD NPCs).
* `--portrait 993:DAMIEN` uses the portrait of the IWD creature (small, else large) for that dialogue.

Copy `<output dir>/modules/<Module>/` into the module folder (runs can be repeated; `skins.json` is merged).

Output:

| path | content |
|---|---|
| `art/interface/dialog_ie/skins.json` | `default` skin, per-dialogue `dialogs` and `portraits` |
| `art/interface/dialog_ie/<skin>/skin.json` | layout (rects in IE design pixels), fonts, colours |
| `art/interface/dialog_ie/<skin>/*.tga` | panel, buttons, scrollbar |
| `art/interface/dialog_ie/portraits/<cre>.tga` | IE portraits of the speakers named with `--portrait` |
| `fonts/ie_*.ttf` | the EE TTF fonts referenced by the skin |

## What is recreated

**iwdee** (from `UI.MENU` menu `WORLD_DIALOG`, `BGEE.lua` styles/colours, MOS/BAM art):

* the framed, translucent dialogue panel anchored above the bottom of the screen (grows upward with the text);
* the portrait slot of the speaker;
* the NPC line in the game log font (PostAntiqua) and colour;
* numbered replies (`1 - ...`) in the EE reply colour, white on hover;
* the history button (top right) that toggles the conversation log over the panel, with highlighted
  speaker names;
* a single `Continue` / `End Dialogue` reply drawn as the EE bottom centre button (`GUIBUTWT`, AmericanUncial).

**iwd** (classic, from `GUIW.CHU` window 7 / `GUIWBTP3`):

* the classic message log panel: the conversation history scrolls up, the NPC line and the replies sit at the
  bottom of the text area;
* the classic scrollbar art (decorative; the mouse wheel scrolls) and the history/"expand" button.

The layout is scaled to the game resolution (the IE design is 1024x768; ToEE often runs smaller).

## Formats

`proto/iegui.py` reads CHU V1, MOS V1/MOSC/V2 (PVRZ) and BAM V1/BAMC/V2 (PVRZ), written from the IESDP
format descriptions.

## Limitations

* Classic installs use BAM fonts; they are not converted, the skin uses a ToEE font instead.
* The `DLGDIVI` divider of the EE menu is not in the tested install and is not drawn.
* Colour conventions (`AABBGGRR` fontcolors, the reply colour from the EE `gsub`) are inferred.
* Fonts: Temple+ loads `fonts/*.ttf` from the module folder when the skin is first used. DirectWrite may
  register a legacy font under a longer family name (Wine reports `R PostAntiqua Roman  05554`), so the
  family is matched by prefix.
