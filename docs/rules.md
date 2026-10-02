# Truco uruguayo — rules spec

Cited rules reference for the engine (`engine/game.py`, `engine/card.py`, `engine/truco.py`).
It exists because the engine was written without a spec; the only prior reference was the
Wikipedia copy in [`wikipedia_truco_uruguayo.md`](wikipedia_truco_uruguayo.md). The engine is
audited against this document in [`engine-rules-audit.md`](engine-rules-audit.md).

**Researched 2026-10-01.** Every quotation below (marked `«…»`) was copied from a page saved
verbatim at fetch time (archive.org `id_` raw snapshots where archived); the quote check is
described at the end of this file.

## How to read this document

Each rule carries one of two tags:

- **SB** — *source-backed*. The sources are listed in parentheses (`S1 Art 8` = source S1,
  article 8; `S3 L142` = line 142 of the repo's Wikipedia copy).
- **CP** — *common practice, no source found*. Stated because the engine needs a position, but
  no fetched source says it. Treat as an assumption.

Where sources disagree, or a rule is a regional/house variant, **every variant is recorded with
its source and none is chosen** — see [§10 Variants register](#10-variants-register). The engine
audit states which variant each finding is measured against.

## Sources

| ID | Source | Variant described | Link (fetch status) |
|---|---|---|---|
| S1 | Web2Mil / ReTruco.com, *Reglamento de ReTruco.com* (cited by Wikipedia ref. 2) | **con muestra**, 1v1 online ("mano a mano"); chico of 20 | <https://web.archive.org/web/20121228153734/http://www.retruco.com/pagina.phtml?pag=ReglamentoRetruco> (200, snapshot 2012-12-28). The original <http://www.retruco.com/pagina.phtml?pag=ReglamentoRetruco> **no longer resolves** (connection failed 2026-10-01); the snapshot is the only copy. |
| S2 | GranAventura.com, *Truco Uruguayo — Reglamento* (cited by Wikipedia ref. 3). Full rulebook: 1v1, 2v2, 3v3, judge, penalties | **con muestra**, 1v1 / pairs / trios; match of three chicos of 40 | <https://web.archive.org/web/20110829054729/http://www.granaventura.com/truco_uruguayo.htm> (200, 2011-08-29). Same text republished as a 2013 blog post, archived <https://web.archive.org/web/20170303124407/http://granaventura.com/blog/2013/04/truco-uruguay/> (200; Art 4 and Art 33 compared identical) |
| S3 | Wikipedia (es), *Truco uruguayo* — the repo copy [`wikipedia_truco_uruguayo.md`](wikipedia_truco_uruguayo.md) | con muestra; 2/4/6 players; 40 points, malas/buenas of 20 | <https://es.wikipedia.org/wiki/Truco_uruguayo> (repo copy used for line numbers) |
| S4 | Conecta Games blog, *Reglas del Truco Uruguayo* (2015; Wikipedia external link) and its current site page | con muestra; 2/4/6 players; "30 or 40" | <https://conectagamesblog.wordpress.com/2015/12/17/reglas-del-truco-uruguayo/> (200); <https://www.conectagames.com/rules/truco_uy> (200). Same publisher as S1 (the blog signs off "ConectaGames by Web2mil") |
| S5 | Ludoteka, *Truco Uruguayo rules* | con muestra; 1v1 and pairs; chico of 30 | <https://www.ludoteka.com/games/truco-uruguayo/rules> (200) |
| S6 | pagat.com, *Uruguayan Truco* (J. McLeod, after A. Taylor) | con muestra; 2/3/4 players; differences from Argentine truco only | <https://www.pagat.com/put/truco_ur.html> (200) |
| S7 | servicioti.com.uy blog post, *Truco Uruguayo Reglamento* (2026-04-04) | con muestra; 2/4/6 | <https://www.servicioti.com.uy/2026/04/truco-uruguayo-reglamento.html> (200). **Not independent**: its tables mirror S3. Cited only as corroboration. |

**Looked for and not usable** (so nobody repeats the search):

- *Dichos Del Truco Reglamento* (Wikipedia ref. 5), archived
  <https://web.archive.org/web/20190114044550/http://www.lekkobooks.com/elibs.php?q=Dichos%20Del%20Truco%20Reglamento>
  (200): an ebook-download/subscription lure page with fake comments and **no rules text**.
  The underlying book is Suárez (1994), *Dichos del Truco* (ref. 4); not available online.
- Fuentes Pereira (2001), *El truco: historia de una tradición*, Sumuntán 14 (Wikipedia ref. 1):
  <https://dialnet.unirioja.es/servlet/articulo?codigo=1249834> (200). It appears in *Sumuntán:
  anuario de estudios sobre Sierra Mágina* (a Spanish region), only a one-line abstract is
  public, and it is not a Uruguayan rulebook.
- Scribd copies of "Reglas y Valores del Truco Uruguayo" (`scribd.com/document/58713096`):
  JavaScript challenge wall, no text retrievable.
- Argentine ministry rulebook, *Truco — Reglamento 2023*
  (<https://www.argentina.gob.ar/sites/default/files/2023/04/truco.pdf>): fetched; Argentine truco
  (the word "muestra" does not appear). Not applicable to the muestra game.
- **No current Uruguayan tournament, federation, or club rulebook was found.** Searches run:
  "reglamento truco uruguayo torneo oficial federación campeonato …", "Asociación Uruguaya de
  Truco reglamento oficial pdf", "Federación Uruguaya de Truco campeonato nacional reglamento
  torneo …", and the `contra flor al resto` / `echar los perros` phrase search. They returned only
  S1–S7 and Argentine material. S2 is the most complete and the closest thing to a formal
  rulebook (judge, penalties, tournament provisions), but it is a 2011 web page, not an
  organisation's current rulebook.

---

## 1. Deck, deal, mano

- 40-card Spanish deck, no 8s, 9s or jokers; suits oro, copa, basto, espada. **SB** (S1 Art 2;
  S2 Art 2; S3 L17).
- 3 cards each, then one more card face up: the **muestra**, whose suit defines the *piezas*.
  **SB** (S2 Art 8: «sacará la carta de la boca y la pondrá a su derecha sobre la mesa boca
  arriba. Esa carta se llama "muestra"»; S1 Art 6; S3 L19, L60).
- **Mano** is the player to the dealer's right and plays first; **pie** is the last to play.
  **SB** (S3 L60, L64, L162–166; S2 Art 8 deals starting «por el primero de su derecha»).
  Play and declaration order run to the right (S3 L64: «sentido antihorario»).
- Players of the two teams sit alternately. **SB** (S2 Art 3; S3 L54).

## 2. Cards: muestra, piezas, hierarchy

### 2.1 Piezas and the 12 rule

- **Piezas** are the 2, 4, 5, caballo (11, *perico*) and sota (10, *perica*) **of the muestra
  suit**. **SB** (S1 Art 8a: «Son los "dos", "cuatro", "cinco", "caballos" y "sotas" cuando sean
  del palo de la muestra»; S2 Art 12a; S3 L19, L27–32).
- **12 rule.** When the muestra card is itself one of those five, the **12 (rey) of the same
  suit takes its value as a pieza «a todos los efectos»**. **SB** (S1 Art 8a: «Cuando sea muestra
  una de las cartas indicadas, el Rey del mismo palo adquiere el valor de ella como "pieza" a
  todos los efectos»; S2 Art 12a; S4: «Si la muestra es una pieza (2, 4,5, 10 u 11), el 12 de
  ese palo toma el valor de la pieza que se encuentra en la muestra»; S5; S6 (the 12 becomes
  «a wild card worth 9» when the 4 is the muestra); S7). S3 does not mention it.
- If the muestra is a 12 (or any non-pieza) the 12s of that suit are ordinary. **SB** (S6: «The 12
  (rey) of the muestra suit has no special value unless the face up card is a 2, 4, 5, 11 or 10»).

### 2.2 Trick hierarchy (strongest first)

**SB** (S1 Art 8; S2 Art 12; S5 table; S3 L27–50 agrees on categories). Categories rank
**piezas > matas > fíos > comunes**; within a category:

| Rank | Cards |
|---|---|
| Piezas | 2 > 4 > 5 > perico (11) > perica (10), all of the muestra suit (plus the 12 standing in for the muestra, §2.1) |
| Matas | as de espada («espadilla») > as de basto («bastillo») > 7 de espada > 7 de oro |
| Fíos | any 3 > the 2s that are not piezas > as de oro and as de copa |
| Comunes | reyes (12) > caballos (11) > sotas (10) (those that are not piezas) > 7 de copa and 7 de basto > 6 > 5 > 4 (the 5s and 4s that are not piezas) |

- Source text for the ordering of the commons: S1 Art 8: «Los reyes valen más que los caballos;
  éstos más que las sotas; éstas más que los siete de copas y bastos; éstos más que los seis;
  éstos más que los cinco y éstos más que los cuatro».
- The 2 of the muestra is the strongest card; a non-muestra 4 is the weakest. **SB** (S1 Art 8).
- Cards of equal rank in different suits (e.g. two 3s) are equal. What equality *does* is a
  source tension, see [V-07](#10-variants-register).

### 2.3 Envido point values per card

**SB** (S1 Art 9; S2 Art 13; S3 L27–50 table; S5):

| Card | Envido points |
|---|---|
| 2, 4, 5 of the muestra | 30, 29, 28 |
| 11 and 10 of the muestra | 27 each |
| the 12 standing in for the muestra | the pieza's value (§2.1) |
| any other card, 1–7 | its number (S1 Art 9b: «Las blancas que no sean piezas, cualquiera sea su categoría, valen por su valor escrito») |
| 10, 11, 12 that are not piezas («negras») | 0 (S1 Art 9c: «Las negras valen cero») |

## 3. Envido

### 3.1 Computing a hand's envido (when no flor is in play)

**SB** (S1 Art 10B; S2 Art 14B; S3 L99–101; S4; S5). Max is 37 (S3 L95, S4).

| Hand | Envido |
|---|---|
| one pieza | pieza value + written value of the highest other card (S1: «Se suma el valor de ésta, el valor escrito de la blanca más alta») |
| no pieza, two cards of the same suit | their two values + 20 (S1 Art 10B-c: «Se suman los valores escritos sobre veinte»; negras count 0) |
| no pieza, three suits | value of the highest card (negras 0, so three negras = 0) |

(The sources' alternatives for hands with two or three piezas are flor hands; §4.)

### 3.2 Who may call and when

- Any player of a team, before playing a card, and without having said «truco» or «quiero» to
  the opponents' truco/envido. **SB** (S1 Art 16: «No haber dicho "truco" o "quiero" al truco o
  envido del adversario»; S2 Art 22; S5: envido is opened «al llegarle el turno para jugar su
  primera carta o responder a una apuesta de truco»).
- A call is made for the whole team. **SB** (S2 Art 21: «el desafío que hace un jugador al
  rival, por sí y por su equipo»).
- **Flor voids envido.** If any player has and calls flor there is no envido; only «con flor»
  bids between flor holders. **SB** (S1 Art 20: «Si sólo canta flor el rival no habrá disputa de
  tantos de "envido"»; S2 Art 27; S3 L146; S4; S5).

### 3.3 Calls, values and the ladder

| Call | Value | Source |
|---|---|---|
| envido | 2 | **SB** S1 Art 18, S2 Art 24, S3 L107 |
| real envido | 3 | **SB** S1 Art 18, S2 Art 24, S3 L108 |
| falta envido | the **falta** (§3.4) | **SB** S3 L109, S1 Art 19, S2 Art 25 |

- **Declined first call: caller scores 1.** **SB** (S1 Art 18: «El envite no aceptado da un punto
  al envidante»; S2 Art 24; S3 L95).
- **Re-raising (revirar / reenvidar).** The challenged side may raise instead of answering; a
  raise counts as an acceptance of the call it answers («quiero» is implicit). The raiser takes
  the role of the caller. Raises may be repeated «tantas veces como se desee». **SB** (S1 Art 25,
  26; S2 Art 34, 35; S3 L111).
- **Payment is the sum** of the amounts accepted: envido+envido = 4, envido+real envido = 5.
  **SB** (S3 L113–120; S2 Art 25: «los envites o reenvites válidos que sean aceptados y por la
  suma de sus importes»; S4).
- **A declined raise pays the raised-against side the sum already accepted**, not the declined
  amount: A envido, B envido, A «no quiero» = 2 to B. **SB** (S3 L111, L117–118; S1 Art 26 / S2
  Art 35: «el reenvite no aceptado no genera ganancia de punto a favor del reenvidante»; S4: «2
  puntos si no se quiere»).
- **Ordering restrictions of the ladder** (e.g. no envido after real envido; falta envido ends
  the ladder) — the sources only say raises must be «por los puntos porque fue envidado como
  mínimo o por más» and that a smaller amount «será siempre por el importe de éste» (S1 Art 26;
  S2 Art 35). Whether falta envido can be raised further is not stated except through the cap in
  §3.4. **CP** for "no going back to a lower call"; see [V-05](#10-variants-register).

### 3.4 Falta and the cap

- **Falta = the points the *leading* side still needs to complete the chico.** **SB** (S3 L109:
  «La cantidad de puntos que le falta al equipo que va primero»; S1 Art 17, 19; S2 Art 23, 25:
  «la cantidad de puntos que expresa el Artículo 23. Esa cantidad queda fijada por los puntos
  que tenga el equipo delantero luego de anotados los resultados de la mano o ronda anterior»).
  Only the leader's score matters, not the caller's.
- **Cap.** A bid beyond the falta is treated as a simple two, and a raise beyond it is valid for
  the preceding amount or the falta, whichever is smaller. **SB** (S1 Art 27; S2 Art 36: «Si en
  un envite el envidante excede la falta … ese envite se tomará como simple de dos tantos. En
  caso de ser excedida la falta en virtud de un reenvite, éste será siempre válido por el
  importe del envite o reenvite que le precede o por la falta si fuera ésta menor»).
- Pico a pico falta is a different number (6 or 10): [V-03](#10-variants-register).

### 3.5 Declaring points and ties

- After a «quiero», **mano declares first**; each following player declares only if they beat
  the best figure announced so far; ties do not beat. **SB** (S1 Art 29–31; S2 Art 39–44; S3
  L95: «sólo si éste supera a los puntajes antes dichos»).
- **The procedure alternates between sides.** Mano declares; then a *rival* of the last declarer
  declares, and only if their figure beats it; then a rival of *that* player must beat it, and so
  on. Teammates of the last declarer do not speak. **SB** (S2 Art 39: «El rival que lo supere
  empezando por su derecha, cantará el suyo y siempre que el último punto cantado sea superado por
  un rival, éste debe cantarlo»; Art 41; Art 44: «cante cifra igual o inferior a la cantada por un
  rival de su izquierda, no pudiendo cantar válidamente su punto»).
- Consequences. The side holding the strictly higher figure always ends up declaring it, so it
  wins. **A tie goes to the side that declared the tied figure first in this procedure**: not
  "mano's side always", and not "the lowest seat holding the maximum" either (e.g. A 30, B 20, A 33,
  B 33 in seat order: B declares 33 first because A's 33 never gets to speak, so B wins; the
  lowest-seat rule would say A). For 1v1 the sources state it outright: **SB** (S5: «En caso de
  empate, gana el jugador que es mano»; S1 Art 14 for flor). For teams the tie outcome is
  **inferred** from the procedure, and Art 39 does not pin down which rival speaks first when
  several could ([V-14](#10-variants-register)).

## 4. Flor

### 4.1 Definition and scoring

**SB** for all (S1 Art 10A, 11; S2 Art 14A, 15; S3 L127–132; S4; S5). A hand is a flor when it
is any of: three piezas; two piezas and any card; one pieza and two cards of the same suit; three
cards of the same suit.

| Hand | Flor points |
|---|---|
| 3 piezas | highest pieza + the units of the other two (30/29/28/27 → 0/9/8/7) |
| 2 piezas + 1 card | highest pieza + units of the other + written value of the third (negra = 0) |
| 1 pieza + 2 cards | pieza + written values of the other two (negras 0) |
| 3 same suit | the three written values + 20 |

Range 20–47 (S3 L134; S4; S7). Worked example (S4): 2 and 5 of the muestra and a 10 of another
suit = 30 + 8 + 0 = 38.

### 4.2 Calling

- Flor must be called **before playing the first card**; holders are obliged to call it. Not
  calling it «niega» the flor: S1 Art 12 gives the three points to the opponent; S2 Art 46–47
  has a longer penalty system. **SB** (S1 Art 12–13; S2 Art 16–18; S3 L125).
- Calling is by the holders themselves, in order from mano; all flor holders announce right
  after the first announcement. **SB** (S2 Art 18; S3 L134). Teammates' flors are announced and
  count (collera = two, trillera = three, S3 L159–160, L198–199).
- A player cannot say «envido» or «truco» without calling the flor they hold (S2 Art 17) — it
  counts as denying it. **SB**.

### 4.3 Points: each flor is worth 3

- **One side only has flor:** the side scores **3 per flor** and there is no envido. **SB** (S3
  L134: «se les acreditan 3 puntos por cada flor»; S2 Art 20, 31, 32; S4).
- **Both sides have flor:** a contest to see whose flor is higher. **SB** (S3 L134). The winner
  collects, for a plain contest, **3 per flor on its own side** (S2 Art 20: «Los puntos de las
  flores de los compañeros de equipo del ganador se sumarán a los de éste»; Art 31) and the loser's
  flors are lost (S5: «Quien pierde el lance no suma los 3 puntos que otorga cada flor»).
  Whether the loser's flors are *also paid to the winner* depends on the call (§4.4).
- **Tie on flor value:** the flor of the side whose caller is «más mano» wins. **SB** (S2 Art 20;
  S1 Art 14: «ganará la del jugador que sea mano»). Flor figures are declared with the same
  procedure as envido figures (S2 Art 40: «los jugadores que la tengan, empezando por el "más mano",
  deberán cantar su punto en la forma fijada en el artículo anterior»), so the same inference as
  §3.5 applies to teams.

### 4.4 The flor ladder: la mía flor, con flor envido, contra flor al resto

S3 L138–142 names three calls; S1/S2 define flor bids through the general envido rules.

| Call | S3 (L138–142) | S1 / S2 | S4 / S5 |
|---|---|---|---|
| *la mía flor* (just announcing and comparing) | «Se cuentan los puntos al final de la mano y son 3 tantos para la flor con más puntos» | flor is simply worth 3 (S1 Art 14; S2 Art 20) and is **not a challenge** that can be declined | S4: «Si el contrincante también tiene FLOR puede responder con Flor, en cuyo caso ganará los 3 puntos el jugador que tenga la Flor de mayor valor» |
| *con flor envido* | «se cuentan los puntos en el momento y son 5 tantos para la flor con más puntos» (= 2 envido + 3 flor) | envido bids «con flor» follow the ordinary envido rules; the winner «cobra el importe de lo envidado aceptado más los puntos de su "flor"» (S1 Art 23; S2 Art 31 adds the teammates' flors) | S5: «Con flor envido» and «Con flor envido la falta», «que funcionan del mismo modo que en el lance de envido» |
| *contra flor al resto* | «la flor ganadora se llevará los puntos que le faltan al que vaya ganando para terminar el partido al igual que en la falta envido» (L142) | «contra flor»: the winner additionally collects the rival's flors (S2 Art 31); «resto» **equals** the falta and is only valid in contra flor bids (S2 Art 33) | S4: the winner «gana el Partido» (see [V-01](#10-variants-register)) |

- **How the resto is computed.** The resto is the falta (§3.4): **the shortfall of the *leading*
  side, not of the caller or the winner.** **SB** (S3 L142; S2 Art 33 + Art 25; S7). S4/S5 differ
  in wording only for the winner-takes-match reading: [V-01](#10-variants-register).
- **Ladder shape.** Order of strength is: la mía flor < con flor envido (and, in S1/S2/S5, con
  flor real envido / con flor falta envido) < contra flor al resto. «Resto» is the falta, which by
  the cap (§3.4) cannot be exceeded, so **contra flor al resto is the top of the ladder and
  nothing re-raises it**. The cap is **SB** (S2 Art 33, 36); that this makes contra flor al
  resto terminal is **inferred**, no source states it in those words. A raise to a lower call
  after a higher one: not described anywhere, **CP** that it is not allowed.
  S2 Art 37 gives the only explicit cross-ladder rule: a player raised on «con flor la falta
  envido» «puede reenvidar "contra flor el resto"».
- **Declining.** A declined «con flor» bid pays the caller their own flor(s) only (S1 Art 24;
  S2 Art 32: «el envidante cobrará sólo el importe de las flores de su equipo»); S4: «el desafiante
  se lleva los 3 puntos de su FLOR y el que no quiso el desafío pierde los puntos de su flor».
  A *re-raise* declined after a «contra flor» pays the points bid plus both sides' flors (S2
  Art 32). **SB**.
- **Envido and flor never mix**: see §3.2.

## 5. Truco

### 5.1 Calls and values

**SB** (S1 Art 42–48; S2 Art 60–66; S3 L89–91; S4; S5; S7): a hand with no truco call is worth 1.
**truco** raises it to 2, **retruco** to 3, **vale cuatro** to 4.

### 5.2 Who may raise, and when

- A truco call may be made by any player in their turn, with a card in hand, after the muestra is
  out; the opponents answer **before** the next card is played. **SB** (S3 L89: «En cualquier
  momento de la mano, un jugador en su turno puede decir truco»; S2 Art 49–50; S1 Art 34–35, 42).
- Valid answers to **truco**: «quiero», «no quiero», or **retruco** only. **SB** (S1 Art 42:
  «a) No quiero. b) Quiero. c) Retruco.»; S2 Art 60). **Vale cuatro is not an answer to truco.**
- Valid answers to **retruco**: quiero / no quiero / **vale cuatro**. **SB** (S1 Art 45: «cuyo
  inciso c) dirá "vale cuatro"»; S2 Art 63). Answers to vale cuatro: quiero / no quiero only
  (S1 Art 46; S2 Art 64).
- **Alternation.** Only the side that was challenged may raise: truco (A) → retruco (B) → vale
  cuatro (A). The side that made the last call cannot raise its own call. **SB** (S1 Art 45:
  «el rival desafiado lanza a su vez nuevo desafío»; S3 L91: «el equipo que aceptó puede …
  decir retruco … el equipo que aceptó este último puede decir vale cuatro»; S4: «los gritos deben
  ser alternados por los equipos, es decir, el que dice Truco no puede decir Retruco»).
- A raise is also an acceptance of the call it answers, and the raise may come right away or in a
  later trick after a «quiero». **SB** (S1 Art 45, 48: «Tanto el "retruco" como el "vale cuatro"
  sin previo "quiero" … se tendrán por aceptación»; S3 L91: «en el momento o en rondas
  posteriores»).
- Envido and truco may be called together; the answer to each is independent (S2 Art 69:
  «Quiero y no quiero» etc.). **SB**.

### 5.3 Payouts

See §7 for the full table. Accepted and played: the winner of the hand takes the value of the
last accepted call (S1 Art 44, 45, 47; S2 Art 62–65).

## 6. Tricks, pardas, mano and pie

- Three tricks, one card per player per trick; the highest card wins and its player leads next.
  **SB** (S1 Art 36, 39; S2 Art 51, 57; S3 L64).
- In team play a team's card in a trick is its highest one. **SB** (S4: «la carta que cuenta es la
  carta más alta jugada por cada miembro de la pareja»; S2 Art 57 compares «cartas mayores» of
  rival players).
- **Parda** (tie between the best cards of the two sides): **the first player in turn order, i.e.
  mano, leads the next trick.** **SB** (S1 Art 39: «corresponderá jugar en primer término la segunda
  carta al "mano"»; S2 Art 57).
- **Winning the hand** — by two tricks, or: **SB** (S1 Art 41; S2 Art 59; S3 L70–81):

| Trick 1 | Trick 2 | Trick 3 | Hand winner |
|---|---|---|---|
| A | A | not played | A |
| A | B | A / B | A / B (the 3rd decides) |
| A | parda | not played | A |
| A | B | parda | A (won the first) |
| parda | A | not played | A |
| parda | parda | A | A |
| parda | parda | parda | mano / the side with the mano |

  (S2 Art 59d: «El equipo que tenga jugador "más mano" en caso de ser parda las tres».)
- **The hand ends as soon as it is decided**: a side that won trick 1 wins if it wins or ties
  trick 2 (S1 Art 40; S2 Art 58).

## 7. Folding and «no quiero» — what the other side collects

| Situation | Points to the side that made the call | Source |
|---|---|---|
| «no quiero» to **envido** / **real envido** (first call) | 1 | **SB** S1 Art 18; S2 Art 24; S3 L95, L116 |
| «no quiero» to a raise of envido | the sum already accepted (e.g. E,E,NQ → 2; E,Real,NQ → 2) | **SB** S3 L111, L117–118; S4 |
| «no quiero» to **falta envido** | the sum already accepted, 1 if it was the first call | **SB** S3 L111 (S7: «Lo acumulado del toque previo») |
| «quiero» to envido | the winner scores the sum of the accepted amounts | **SB** S3 L113–121 |
| «no quiero» to **con flor** (first call) | the caller's own flor(s), 3 each | **SB** S1 Art 24; S2 Art 32; S4 |
| declined re-raise after **contra flor** | points bid + both sides' flors | **SB** S2 Art 32 |
| «no quiero» to **truco** | **1** | **SB** S1 Art 43; S2 Art 61; S3 L89 |
| «no quiero» to **retruco** | **2** (the accepted truco) | **SB** S1 Art 45; S2 Art 63 |
| «no quiero» to **vale cuatro** | **3** (the accepted retruco) | **SB** S1 Art 46; S2 Art 64 |
| accepted and played | 2 / 3 / 4 for the hand winner | **SB** S1 Art 44, 45, 47 |
| going to the mazo with a truco challenge pending | counts as «no quiero» (tacit) | **SB** S1 Art 42–43; S2 Art 60–61 |
| going to the mazo with no challenge pending | 1 point to the opponent | **CP** (S1 Art 52 says only «el punto se le otorgará a su contrincante» for an online player who leaves) |
| a team member goes to the mazo without saying «paso» | the whole team is out of play for that round | **SB** S2 Art 90 |

## 8. Match length, malas and buenas

- The unit is the **chico**; the first half of its points are the **malas**, the second half the
  **buenas**; the chico goes to the first to reach its total. **SB** (S1 Art 4; S2 Art 4; S3 L56).
- Length varies by source: **20 per chico (40 in championships)** (S1 Art 4), **three chicos of 40,
  best of three** (S2 Art 4), **a single 40** divided in two halves of 20 (S3 L56, S7), **30 or 40**
  with halves of 15/15 or 20/20 (S4), **chico of 30** (S5). See [V-04](#10-variants-register).
- Malas/buenas drive the 6-player redondilla / pico a pico alternation (§9). **SB** (S2 Art 83; S3
  L66–68). That they have no other rule effect (nothing for 1v1/2v2) is an inference: no source
  attaches one. **CP**.
- The falta and the resto are measured against the chico's total (§3.4).

## 9. Teams, 6-player formats, and señas (only as far as legality)

- Teams of 1, 2 or 3. **SB** (S3 L54; S2 Art 3).
- **6 players: redondilla and pico a pico.** Until one side has reached half the chico, rounds
  alternate: a general round (3v3, redondilla), then 1v1 rounds against the facing opponent
  (pico a pico); the first round of each chico is general; after half, only redondillas.
  **SB** (S3 L66–68; S2 Art 83, 84; S4; S7). Falta/resto limits in the 1v1 rounds: [V-03](#10-variants-register).
- **Team calls bind the team**; a player's «paso» takes them (and their remaining cards) out,
  leaving the rest of the team to carry on. **SB** (S2 Art 21, 68, 88–90; S3 L186–187).
- **Señas** are a table of gestures for passing card information within a team (S2 Art 102;
  S3 L21, 27–50; S6). They do not change which actions are legal; what they bound is that teammates
  **may not show each other their cards** (S2 Art 102). Only the rule effect is recorded; the
  gestures themselves are in S3/S6 and are not repeated here. **SB**.

## 10. Variants register

None of these is resolved here. "Engine" says what the engine does since the audit fixes: S2 is the
base where sources disagree, and the variants that change benchmark numbers are `engine.rules.Rules`
knobs (defaults named below).

| ID | Topic | Variants (source) | Engine |
|---|---|---|---|
| V-01 | **What contra flor al resto pays** | (a) «los puntos que le faltan al que vaya ganando para terminar el partido» — leader's shortfall (S3 L142; S7; S2 Art 33 + 25) · (b) the winner «gana el Partido» (S4; S4 site: «Contra Flor al Resto: the winner takes the match»); S5/S4 add that declining loses the flor points · (c) S2 Art 31: also adds the rival's flors | (a) + (c): the resto is the leader's shortfall (`rules.falta`); an accepted contra flor al resto pays the resto plus both sides' flors (S2 Art 31). (b) is not offered |
| V-02 | **Flor-ladder calls available** | S3: three calls (la mía flor, con flor envido, contra flor al resto). S1/S2/S5: envido-style bids apply «con flor» (S5 names «con flor envido» and «con flor envido la falta») | S1/S2/S5: the whole envite ladder «con flor» (envido, real envido ×1/×2/×3, hasta igualar, falta envido) plus contra flor al resto |
| V-03 | **Falta / resto in pico a pico** | S3 L66: «la Falta Envido serán 6 puntos, mientras que la Contra Flor al Resto serán 12 puntos (6 pts. + las 2 Flores)» · S2 Art 86: «"la falta" y "el resto" quedan limitados a la cantidad de diez tantos» | `Rules.pico_falta_cap`, default **10** (S2 Art 86); 6 selects S3 (its resto of 12 = 6 + the 2 flors falls out of the contra flor payout) |
| V-04 | **Match length** | 20/chico, 40 in championships (S1) · 3 chicos of 40 (S2) · one 40 (S3, S7) · 30 or 40 (S4) · chico of 30 (S5) | `Rules.chico_points` (default 40) and `Rules.chicos_to_win` (default 1 = S3; 2 = S2's best of three) |
| V-05 | **Envido raise order** | S1 Art 26 / S2 Art 35: any raise «por los puntos porque fue envidado como mínimo o por más», repeatable at will; a lower amount counts as the preceding one (S2 Art 35) · S3 lists the three calls in ascending order and gives no explicit rule | a raise must be at least the call it answers (S2 Art 35), repeatable; totals capped at the falta (Art 36); once the falta is reached only contra flor al resto remains, in a flor contest (Art 37) |
| V-06 | **«Chumbo»** | S3 L66 / S7: «los revires se anulan a los 6 pts si alguno revira con falta envido» (an agreed 6-point cap in pico a pico) | not implemented |
| V-07 | **Equal cards in a trick** | S1 Art 8 / S2 Art 12: S1 Art 8: «Entre cartas de igual valor, gana la del jugador que sea "mano"»; S2 Art 12: «gana la del jugador que sea más "mano"» — vs S1 Art 39 / S2 Art 57: equal best cards «la basa quedó empatada o "parda"». S1/S2 contain both; no source reconciles them | equal strength = parda (`card.py` docstring) |
| V-08 | **Flor on/off** | **No source found describing a ruleset without flor.** S1–S7 all include it. | flor is always on |
| V-09 | **Echar los perros / «a ley de juego»** | pre-deal challenge of falta envido / contra flor al resto / truco (S2 Art 70–82; S4; S7; S4 site) | `Rules.ley_de_juego`, default **off**: the seven bundles of S2 Art 73, answered all / in part / none (Art 75) |
| V-10 | **Real envido multiplier, «hasta igualar»** | S2 Art 24 («se le antepone una cifra superior a uno, será por el importe de ella multiplicada por tres»); S1/S2 «hasta igualar envido» | «dos / tres real envido» (×2, ×3) and «hasta igualar»; free-form «N tantos envido» amounts are not offered |
| V-11 | **12-as-pieza** | S1, S2, S4, S5, S6, S7 yes; S3 silent | implemented (`truco.py:es_pieza`) |
| V-12 | **Number of players** | 2, 4, 6 (S3, S4); 1v1, pairs, trios (S2); also 3 (mano alone against two, with a fourth card) (S6) | 6 players only; mano-a-mano pairs exist only inside a 6-player match |
| V-13 | **Stake of a declined flor challenge** | caller's own flors only (S1, S2); caller's flors, loser forfeits theirs (S4); S3: 3/5 tantos for the winning flor, silent on declines | S1/S2: a declined first call pays the caller's side's flors; a declined raise adds the tantos already accepted, and a declined contra flor raise also the rival's flors (S2 Art 32) |
| V-14 | **Who speaks first on the responding side (envido/flor figures)** | S2 Art 39: after a declaration, «obligado en primer término quien ocupa el lugar de "más mano" a la izquierda de aquél si lo hubiere y en caso contrario el primero de la derecha». Two readings: (a) the rival nearest to the right of the declarer who beats the figure; (b) the most-mano (lowest seat) rival who beats it. Both give the same winner except in rare cases (audit A-05 measured them within 7 deals of 200 000) | reading (b): the most-mano rival who beats the figure (`rules.declaration_winner`) |

## Quote check

Every `«…»` quotation above was verified to be a substring of the saved source text (whitespace,
markdown emphasis and typographic quotes normalised), by the script run before commit; quotations
attributed to S3 are checked against `docs/wikipedia_truco_uruguayo.md` itself.
