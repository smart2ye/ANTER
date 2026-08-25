from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_comment_composer_keeps_feedback_below_the_input_row():
    template = (PROJECT_ROOT / "app/templates/comments.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "app/static/css/style.css").read_text(encoding="utf-8")

    assert 'class="comment-form comment-composer"' in template
    assert 'class="comment-composer-row"' in template
    assert 'class="comment-composer-feedback d-block text-muted mt-2"' in template
    assert 'class="comment-composer-voice-preview mt-2 small text-danger d-none"' in template

    comment_form_rule = stylesheet.split('.comment-form {', 1)[1].split('}', 1)[0]
    assert 'display: flex' not in comment_form_rule
    assert '.comment-composer-row {' in stylesheet
    assert '.comment-composer-feedback,' in stylesheet
    assert '@media (max-width: 420px)' in stylesheet
