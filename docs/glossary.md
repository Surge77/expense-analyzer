# Glossary

Plain-English definitions of every term this project uses without explaining.
If something here is still unclear, that is a bug — please open an issue.

## Measurement

**Accuracy** — the share of predictions that were right. Easy to read and easy
to be fooled by. If 43% of transactions are Food, a model that answers "Food"
every single time scores 43% accuracy while having learned nothing.

**Precision** — of the things the model *called* Food, what share really were.
Low precision means it cries Food too readily.

**Recall** — of the things that really *were* Food, what share it found. Low
recall means it misses them.

These trade off. A model that predicts Food exactly once, correctly, has 100%
precision and terrible recall.

**F1** — one number combining precision and recall (their harmonic mean, which
punishes a bad score on either). 1.0 is perfect, 0.0 is useless.

**Macro F1** — the F1 of each class, averaged, **giving every class an equal
vote**. This is the number to read here. The always-Food model scores 0.050,
because it fails all eleven other classes and macro F1 refuses to let the one
big class hide that.

**Weighted F1** — the same average, but classes count in proportion to their
size. Sits between accuracy and macro F1.

**Confusion matrix** — a grid of what was actually X against what was predicted
as Y. The diagonal is correct answers; everything off it is a specific mistake
you can go and look at.

**Baseline** — the dumbest thing that could work, scored honestly, so a real
result has something to be compared against. Here it is "always answer with
the commonest class". A model that cannot beat it has contributed nothing.

## Data preparation

**Training set / test set** — the model learns from the training set and is
scored on the test set it has never seen. Scoring on data it trained on
measures memory, not learning.

**Stratified split** — splitting so each class keeps the same proportion in
both halves. Without it, a class with 20 examples can land entirely in the
training set, and the test set can then contain a class the model never saw.

**Cross-validation** — splitting the training data several ways and scoring
each, to check the result was not one lucky split. "5-fold" means five splits.
A large spread between folds means the number is fragile.

**Class imbalance** — some categories being far more common than others. Food
is 43% of this dataset and Family is roughly 1%. Imbalance is what makes
accuracy misleading and macro F1 necessary.

**Class weights** — telling the model that mistakes on rare classes cost as
much as mistakes on common ones. `class_weight="balanced"` does this
automatically. Here it costs 2 points of accuracy and buys 4 of macro F1.

## The model

**TF-IDF** — *term frequency times inverse document frequency*. A way of
turning text into numbers. A word scores highly for a transaction if it
appears often in that description (term frequency) **and** rarely across all
the others (inverse document frequency). So "the" scores near zero, and
"rickshaw" scores highly for the few rows containing it.

**n-gram** — a run of n adjacent items. Word 2-grams of "mutual fund A" are
"mutual fund" and "fund A". Character 3-grams of "dosa" are "dos" and "osa".

**Character n-grams** — matching on fragments rather than whole words. They
handle typos, abbreviations and transliteration: "rikshaw" never appears in
training, but it shares most of its fragments with "rickshaw", so it still
lands in the right place.

**Logistic regression** — a model that learns a weight for every feature and
adds them up to score each class. Chosen here because those weights are
readable: `model.top_features_for()` prints the words it actually leans on,
which is how you catch it learning something silly.

**Pipeline** — vectoriser and classifier bolted into one object, so the exact
same transformation is applied at training and prediction time. Applying them
separately is a classic way to get quietly wrong results.

## This project

**Narration** — whatever the bank printed to describe a transaction, such as
`UPI-SWIGGY-swiggy@icici-512334`. Also called "transaction details".

**Categorisation rules** — the hand-written keyword table in `categorize.py`
mapping merchant names to categories. Domain knowledge that exists nowhere in
the data.

**Coverage** — how much of a statement the rules matched at all. Distinct from
accuracy: coverage says nothing about whether a match was *correct*. Measuring
coverage without ground truth is the limitation that motivated the benchmark.

**Schema** — which columns a particular bank's export uses, kept as data in
`data/schemas.py` so adding a bank does not mean editing the parser.
