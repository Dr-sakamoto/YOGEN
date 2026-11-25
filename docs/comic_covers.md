# アメコミ表紙の分析（マーベル 1970〜90年代前半）

YŌGEN をアメコミ風にするための下調べ。対象は 1970〜1993 年のマーベルの月刊誌の表紙。

## 0. 調べ方

- 6 誌（Amazing Spider-Man / Fantastic Four / Avengers / Incredible Hulk / Captain America / Daredevil）から
  16 号おきに抜き出した **91 枚** の表紙の画像を見て測った。
  - 画像：Marvel Database（marvel.fandom.com）の表紙画像。
  - 号ごとのデータ（価格、表紙の文言、表紙の文字を書いた人）：Grand Comics Database（GCD）の API。
- 位置と大きさは、表紙の幅・高さを 100 とした割合（x＝左から、y＝上から）。
  - 12 枚は 5% 刻みの方眼を重ねて目で測った。
  - 左下のバーコード欄は 91 枚すべてを機械で測った。
- 画像は調査用に手元に置いただけで、リポジトリには入れていない（著作権のある表紙なので素材にはしない）。

> 実物の表紙・ロゴ・キャラクターは素材として使わない（CLAUDE.md の画像の決まり）。ここで借りるのは「型」だけ。

## 1. 画面の骨組み（実測）

```
 x: 0      18                                   100
y 0 ┌───────┬──────────────────────────────────┐
    │       │ MARVEL COMICS GROUP の帯（〜1983）  CCA│ ← y0〜5
    │コーナー│ 冠の語・シリーズの合言葉               │
    │ボックス│ 題字（ロゴ）                         │ ← y5〜30
 30 ├───────┴──────────────────────────────────┤
    │ 煽り文（題字の真下・爆発形）・フキダシ           │
    │                                          │
    │            絵（自由に使える面）               │ ← y30〜80
    │                                          │
 80 ├───────┐                                  │
    │バーコード│        下の煽り文（大きな太字）       │ ← y80〜100
100 └───────┴──────────────────────────────────┘
```

| 部品 | 位置・大きさ（測った値） | 変化 |
|---|---|---|
| コーナーボックス | x0〜15/20、y0〜27/32 | 幅は 70 年代 15〜17% → 80 年代後半〜90 年代 18〜20%。高さは一貫して表紙の約 3 割。 |
| 上端の帯「MARVEL COMICS GROUP」 | ボックスの右から右端まで、y0〜5 前後 | 1972 年ごろ〜1983 年ごろ。左端に小さく誌名、右端にコミックス・コードの印（x88〜97、y0〜7）。 |
| 題字（ロゴ） | x18〜97、上端 y2〜14、下端 y22〜33 | 高さは表紙の 17〜27%。90 年代は上に企画名や見出しが乗り、題字が下にずれる。 |
| バーコード欄 | 1976〜80：x2〜16、y83〜98／1981〜93：x2〜19、y79〜98 | 1975 年までの 23 枚には無い。初出は 1976 年の号（下の表）。80 年代に少し大きくなる。 |
| 下の煽り文 | y80〜100。バーコード欄の右か、絵の下端 | 70 年代から 90 年代まで続く定位置。 |

**まとめると**：上 3 割は「ボックス＋題字」の帯、左下の 2 割角はバーコード。絵が自由に使えるのは
**y30〜80 の真ん中 5 割と、右下**。文字の面積は、帯（約 30%）に煽り文とフキダシを足して、70 年代は表紙の
3〜4 割、80 年代は 2〜3 割（フキダシがほぼ消える）、90 年代は企画名の帯と爆発形が増えてまた 3 割台に戻る。

## 2. 商業的な部品

### バーコード欄（91 枚の機械測定）

| 年 | バーコード欄のある表紙 / 枚数 |
|---|---|
| 1970〜1975 | 0 / 23（HULK 134・DD 97 は絵の黒い部分の誤検出） |
| 1976 | 2 / 4（CAP 201・HULK 203、どちらも 1976 年後半の号） |
| 1977〜1980 | 11 / 12 |
| 1981〜1993 | 46 / 52（検出されなかったのは直販版の顔の絵や白い枠の号） |

- 手元の画像ではバーコードの部分が黒い四角や白い枠になっているものが多く、縞そのものは見えない。
  直販版（専門店向け）では、同じ位置にキャラクターの顔の絵が入る。
  - DD 153（1978）：デアデビルの顔
  - ASM 299（1988）：スパイダーマンの顔（線画）
- 1976 年 6 月号ごろから入ったという資料の記述と食い違わない。

### コーナーボックスの中身（上から）

- **70 年代**（帯のある時期）
  - 価格を大きく（「20¢」「30¢」）、その横に号数と月（「129 / FEB」）。
  - 小さく流通コード（「02457」など、雑誌ごとの番号）。
  - 下半分は主役の全身像。
- **1983 年ごろ以降**：帯が消え、ボックスの一番上に赤い「MARVEL」のロゴが入る。
  - 中は顔の絵（Avengers なら 6 人の顔を格子に並べる）。
  - 価格・号数・月の横に、コミックス・コードの印。
- **1990 年ごろ以降**
  - 一番上のロゴは「MARVEL COMICS」の四角いロゴ。
  - 価格は「$1.00 US / $1.25 CAN」のように 2 か国表記（1986〜87 年から）。1992 年からはポンド表記も入る。

### 価格（GCD の記録、通常号）

| 年 | 価格 |
|---|---|
| 1970〜71 | 15¢ |
| 1972〜73 | 20¢ |
| 1974〜75 | 25¢ |
| 1976 | 30¢ |
| 1977〜78 | 35¢ |
| 1979〜80 | 40¢ |
| 1981 | 50¢ |
| 1981〜84 | 60¢ |
| 1985 | 65¢ |
| 1986〜89 | 75¢ |
| 1988〜91 | $1.00 |
| 1992〜93 | $1.25 |

- 1971 年に 1 号だけ 25¢（DD 81、ページ増の号）。
- 記念号は高い：
  - FF 200（1978）：60¢
  - CAP 350（1989）：$1.75
  - HULK 400（1992）：$2.50

### 号の格を上げる部品

- 記念号の飾り：「SUPER-SIZED 350TH ISSUE!」「100TH ISSUE SPECIAL」。
- 90 年代は右上の角に斜めの帯（「THE COUNTDOWN TO SPIDEY'S 30TH ANNIVERSARY BEGINS!」）や、
  「30TH ANNIVERSARY」の印。
- 90 年代は、題字の上に複数の誌をまたぐ企画名の帯が乗る。
  - 「ACTS of VENGEANCE!」
  - 「OPERATION: GALACTIC STORM PART 1」
  - 「MAXIMUM CARNAGE PART …」
  - 「CARNAGE: THE CONCLUSION」

## 3. タイポグラフィ

- **題字**：誌ごとに固定の手描きロゴ。
  - 立体の押し出し、2 重の縁取り、遠近（Daredevil、Captain America）、斜めの配置（80 年代末の Spider-Man）。
  - 色は号ごとに変える。
  - 70 年代は「and the BLACK WIDOW」「and the FALCON」のように相棒の名前を題字の一部として組む。
- **冠の語・合言葉**：題字の上か下に、題字の 1/4〜1/3 の大きさで入れる。
  - 冠の語：「the AMAZING」「THE MIGHTY」「THE INCREDIBLE」。
  - 誌の合言葉：「THE WORLD'S GREATEST COMIC MAGAZINE!」（FF）、「EARTH'S MIGHTIEST HEROES!」（Avengers）、
    「THE MAN WITHOUT FEAR!」（DD）。
- **煽り文**：手描きの大文字。
  - 太い斜体、文末は「!」。
  - 一番言いたい語だけ大きく・色を変える（「KILL SPIDER-MAN!」の KILL、「the JACKAL!」）。
  - 入れ物は黄色・白の四角、ギザギザの爆発形、旗の形。
- **フキダシ**
  - 70 年代：1 枚に 2〜4 個。登場人物が状況を説明する。
  - 80 年代：ほぼ消える。
  - 90 年代：一言の吹き出しが少し戻る（「—I KILLED HIM WELL!」）。
- **表紙の文字を書いた人**（GCD の記録、70 年代）：Sam Rosen（〜1972）、John Costanza、
  Gaspar Saladino、Danny Crespi、Morrie Kuramoto、Irv Watanabe など。どれも手描きのレタリング。

## 4. 文言（実際の表紙から）

GCD に記録されている 70 年代の表紙の題（表紙に書かれた見出し）：

- 「The Monster from the Lost Lagoon!」「The Coming of the Over-Mind!」「Cry Hulk! Cry Havok!」
- 「Death Is a Black Widow!」「Queen of the Werewolves!」「Havoc in the Hidden Land!」「Assault on Psyklop!」
- 「Ternak! The Monster Who Walks the Midnight Snows!」「Death Is the Cobra and Mr. Hyde!」「The Man-Bull Busts Loose!」

→ **ほぼ全部が「!」で終わる**。形は 2 つ：

- 「名詞句＋!」（○○の怪物／○○の女王）
- 「Death Is ___!」型の言い切り

画像から読んだ煽り文：

| 型 | 実例 |
|---|---|
| 任務・脅威の宣告 | 「HIS ASSIGNMENT: KILL SPIDER-MAN!」「THE MOST LETHAL HIRED ASSASSIN EVER!」 |
| 意外性 | 「THE SHOCKER YOU NEVER EXPECTED TO SEE!!」「THE MOST UNEXPECTED SHOCK ISSUE OF THE FANTASTIC FOUR」 |
| 長い前振り＋名前 | 「AND BEHIND THE MOST MURDEROUS PLOT OF ALL TIMES, THERE LURKS… THE JACKAL!」 |
| 対戦の紹介 | 「AND IN THIS CORNER: THE AWESOME METALLOID!」「SIDE-BY-SIDE WITH CHANCE!」 |
| 警告 | 「BEWARE THE HAWK RIDERS!」「OUT OF CONTROL!」 |
| 新登場 | 「INTRODUCING THE NEW CAPTAIN AMERICA AND BUCKY!」 |
| 出演者の一覧（90 年代） | 「FEATURING: VENOM AND CARNAGE (AMERICA'S FAVORITE KILLER SYMBIOTES)」 |
| 自分で突っ込む冗談（90 年代） | 「STILL SO AWESOME WE HAD TO PUT HIS NAME ON THE COVER TWICE AGAIN!」 |

- 記号は `!`、`!!`、`—`、`…` を多用する。
- 70 年代は「…」でためてから名前を出す長い煽りが多い。
- 90 年代は短い見出しと、ふざけた小さな注釈の組み合わせが多い。

## 5. YŌGEN に持ち込むなら（案）

- **コーナーボックス**：左上の幅 18%・高さ 30%。
  - 一番上に篆書の「妖幻」。
  - 価格の位置に年代（「1830s」など）を一番大きく。
  - 号数の位置に回の番号（「No. 07」）、絵の位置に主役の妖怪の切り抜き（網点）。
- **上端の帯**：70 年代型にするなら y0〜5 に「YŌGEN — PHANTOMS OF THE FLOATING WORLD」の帯。右端に自前の印。
- **題字**：y5〜30 に、小文字の yōgen を藤黄の地に黒（ブランドの決まりどおり）。立体の押し出しは墨。
  - 「the AMAZING」の位置に、その回の冠の語を入れる（例「the HAUNTED」）。
- **煽り文**
  - 題字の真下に 1 本、下端（y80〜100）に大きく 1 本。どれも大文字・「!」止め。
  - 70 年代の「AND BEHIND…THERE LURKS… ___!」型の前振りは、妖怪の紹介と相性がいい。
  - 事実は `research_notes` からだけ取る。「〜という説がある」系の話を煽りの看板にしない。
- **バーコード欄**：x2〜19、y79〜98 に飾りの UPC 風の縞。
  - 数字は回の ID や年代にする。本物の UPC 番号は使わない。
  - 直販版のように、同じ枠に妖怪の顔の線画を入れる手もある。
- **コードの印**：「APPROVED BY THE COMICS CODE AUTHORITY」の代わりに自前の印（例「PUBLIC DOMAIN / VERIFIED」）。
  実在の機関の印は真似ない。
- 網点・切り抜き素材は今のレシピのまま。アメコミの網点（ベン・デイ・ドット）とも相性がいい。
- **9:16 に合わせるなら**：上の帯（ボックス＋題字）とバーコード欄は横幅を基準に同じ大きさで置き、
  縦に伸びた分は真ん中の絵の面に回す。
  - 表紙の比 1:1.54 → 1:1.78 で、絵の面は y30〜80 の 5 割から 6 割弱に広がる。

## 出典

- [GoCollect: Newsstand Editions vs. Direct Comics – A History](https://gocollect.com/blog/newsstand-editions-vs-direct-comics-a-history)
- [Quality Comix: Newsstand & Direct Edition Comics](https://www.qualitycomix.com/learn/newsstand-direct-edition-comics)
- [CBR: Why Was Spider-Man's Face on Marvel Corner Boxes in the 1980s?](https://www.cbr.com/why-was-spider-mans-face-on-marvel-corner-boxes-in-the-1980s/)
- [CBR: Best uses of the Marvel corner box](https://www.cbr.com/marvel-best-uses-of-iconic-marvel-comics-corner-box/)
- [GoCollect: Unappreciated Art – Newsstand Comic Books Corner Art](https://gocollect.com/blog/unappreciated-art-newsstand-comic-books-corner-art)
- [Grand Comics Database API](https://www.comics.org/api/)（号ごとの価格・表紙の題・レタラー）
- [Marvel Database](https://marvel.fandom.com/)（表紙画像）
- [13th Dimension: 13 covers to celebrate National Barcode Day](https://13thdimension.com/13-covers-to-celebrate-national-barcode-day/)
