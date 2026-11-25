from yogen import collage


def test_genome_varies_and_is_reproducible():
    a, b, c = collage.sample_genome(1), collage.sample_genome(1), collage.sample_genome(2)
    assert a == b and a != c
    assert abs(sum(a.mix.values()) - 1) < 1e-6 and 1 <= len(a.accents) <= 3


def test_novelty_penalises_repeats_and_scores_are_separate(tmp_path):
    g = collage.sample_genome(3)
    img, trace = collage.render(g)
    assert img.size == (collage.W, collage.H)
    ae = collage.aesthetic(img, trace, g)
    assert 0 <= ae["total"] <= 1
    f = collage.features(img, g)
    assert collage.novelty(f, []) == 1.0
    assert collage.novelty(f, [f]) == 0.0
    g2 = collage.sample_genome(4)
    f2 = collage.features(collage.render(g2)[0], g2)
    assert collage.novelty(f2, [f]) > 0.2


def test_generate_keeps_and_records_history(tmp_path):
    recs = collage.generate(2, 1, tmp_path, seed0=10, min_aesthetic=0, log=lambda *_: None)
    assert len(recs) == 1 and (tmp_path / f"{recs[0]['name']}.png").exists()
    assert len(collage.load_history(tmp_path)) == 1
