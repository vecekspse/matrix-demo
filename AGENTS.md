# AGENTS.md – AI generátor animací pro LED matici 64×64

## Cíl projektu
Na Raspberry Pi 4 s RGB LED maticí 64×64 (Waveshare, knihovna `rgbmatrix`) přehrávat
animace, které vytváří AI. Princip: **nápad → AI napíše malý Python modul → ověříme
ho → přehrávač ho zobrazí → po čase následuje další.**

Projekt už existuje (repozitář na GitHubu) a displej je zapojený a odzkoušený.
**Nejdřív si přečti stávající kód a konfiguraci. Co funguje, nepřepisuj.**
Hodnoty pro displej (`gpio_mapping`, `gpio_slowdown`, `pwm_bits`, `brightness`…)
převezmi z funkčního kódu v repozitáři a neměň je bez výslovného pokynu.
Vodítko z dokumentace: na Pi 4 `gpio_slowdown` ≥ 4, jas pro trvalý provoz 30–60.

## Architektura (dodrž oddělení)
```
generator/   volá AI, skládá prompt, opravná smyčka, ukládá do library/
runner/
  contract.py   konstanty a kontrakt animace
  validate.py   statická kontrola + zkušební běh v podprocesu
  preview.py    offscreen render do GIF/PNG (na PC, bez rgbmatrix)
  player.py     JEDINÉ místo, kde se importuje rgbmatrix
library/      schválené animace: <name>.py + <name>.json (metadata)
rejected/     zamítnuté animace s důvodem (pro ladění promptů)
```
- Generování a přehrávání jsou **nezávislé procesy**. Přehrávač nikdy nečeká na AI,
  hraje z `library/`. Když generátor nebo síť nefunguje, displej hraje dál.
- Kód od AI **nikdy** nespouštěj v procesu přehrávače. Každá animace běží v podprocesu
  s časovým limitem. Při pádu nebo timeoutu přehrávač přejde na další animaci.

## Kontrakt animace (jeden soubor = jedna animace)
```python
NAME = "plasma_ocean"   # krátký název, a-z 0-9 _
DURATION = 45           # sekund
FPS = 20                # 10–30

def init(w, h):
    """Zavolá se jednou. Vrátí stav (dict). Žádné I/O."""
    return {"seed": 42}

def render(state, t):
    """Vrátí numpy pole tvaru (64, 64, 3), dtype uint8, RGB. t = čas v sekundách.
    Čistá funkce: výsledek závisí jen na state a t."""
```
Pravidla pro AI-generovaný kód:
- Povolené importy: `numpy`, `PIL`, `math`, `random`, `colorsys`. Nic jiného.
- Zakázáno: `open`, `exec`, `eval`, `compile`, `__import__`, přístup na `__atributy__`,
  `os`, `sys`, `subprocess`, `socket`, jakákoli síť a soubory.
- Žádné cykly přes jednotlivé pixely. Používej vektorizovaný numpy (`np.mgrid`, `np.sin`…).
- Rozpočet: `render` do 40 % časového rámce snímku (při 20 FPS ≤ 20 ms) na Pi 4.
- Vizuálně: 64×64 je malé. Žádné 1px detaily, vysoký kontrast, tmavé pozadí, sytější barvy.
  Animace se plynule opakuje nebo má smysluplný konec.
- Gamma korekci a jas řeší **přehrávač**, animace posílá lineární RGB 0–255 a jas neřeší.

## Co má dělat validátor (`runner/validate.py`)
1. Rozbor kódu přes `ast`: povolené importy, zakázaná jména a atributy, přítomnost
   `NAME`, `DURATION`, `FPS`, `init`, `render`.
2. Zkušební běh v **podprocesu** s limitem času a paměti (`resource.setrlimit`, `timeout`):
   alespoň 100 snímků offscreen.
3. Kontrola výstupu: tvar `(64,64,3)`, `uint8`, měřený čas snímku, snímek není celý
   černý, animace není úplně statická, žádné výjimky.
4. Výsledek jako strukturovaný JSON (ok / seznam chyb). Chyby slouží jako zpětná
   vazba pro AI.
5. Pozn.: kontrola přes `ast` není skutečný sandbox. Ochranou je podproces s limity
   a neplatí na ní, že by kód od AI byl důvěryhodný.

## Generátor (`generator/`)
- Vstup: nápad (text) nebo náhodné téma ze seznamu. Výstup: modul podle kontraktu.
- Prompt pro AI obsahuje kontrakt výše, rozlišení, pravidla a jeden krátký funkční příklad.
  AI vrací **jen kód v jednom bloku**, bez vysvětlování.
- Opravná smyčka: při chybě validátoru pošli AI původní kód + chybu, maximálně 3 pokusy.
  Pak zahodit do `rejected/` i s důvodem.
- K animaci ulož `<name>.json`: prompt, model, datum, výsledky validace, FPS, průměrný
  čas snímku. Později se hodí pro výběr a statistiku.
- Generování dávkově dopředu (např. 20–50 kusů), ne „na požádání". Je to levnější
  a robustnější.

## Přehrávač (`runner/player.py`)
- Načte `library/`, vybírá náhodně a nezobrazuje opakovaně to samé po sobě.
- Dvojité bufferování (`SwapOnVSync`), pole z `render` převést na `PIL.Image` a poslat
  přes `SetImage`.
- Snímky se časují podle reálného času. Když je `render` pomalý, **vynechej snímky**,
  nezpomaluj animaci.
- Gamma LUT (~2,2) a maximální jas se aplikují tady. Jas je konfigurovatelný.
- Volitelně: fronta uživatelského textu, který se čas od času překryje přes animaci.
- Spuštění vyžaduje `sudo`. Nezapomeň na správný interpret (venv) při `sudo`.
- Čistý konec při Ctrl+C: zhasnout matici.

## Vývoj a testování
- Vyvíjej a testuj na PC. `preview.py` vykreslí animaci offscreen do GIF (zvětšený
  např. 8×, nearest-neighbor), aby šla posoudit okem.
- Na Pi se nasazuje až ověřený obsah. Nezkoušej nový kód rovnou na displeji.
- Závislosti: `numpy`, `Pillow`. Držet minimální. Verze zapsat do `requirements.txt`.

## Postup práce (po krocích, po každém ukaž výsledek)
1. Projdi existující repozitář a shrň, co už je hotové.
2. `contract.py` + `validate.py` + `preview.py` s jednou ručně napsanou ukázkovou animací.
3. `player.py` přehrávající `library/` v podprocesech.
4. `generator/` s opravnou smyčkou a ukládáním metadat.
5. Smyčka: generování na pozadí, přehrávač čte `library/`.

## Hotovo, když
- Ručně vybraná ukázka i 10 animací od AI projde validací a běží na displeji bez
  blikání a pádů.
- Pád jedné animace nezastaví přehrávání.
- Přehrávač běží hodinu a víc na jednom spuštění bez nárůstu paměti.

## Zásady pro agenta
- Dělej malé kroky, drž se kontraktu a nevymýšlej nové funkce navíc.
- Nic nemaž a nepřepisuj existující funkční kód bez zeptání.
- Nikdy neukládej API klíče do repozitáře. Používej proměnné prostředí nebo `.env`
  mimo git.
- Když si nejsi jistý parametrem displeje, ptej se a nehádej.