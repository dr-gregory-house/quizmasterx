# main/routes.py
from flask import Blueprint, render_template, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def hello():
    marathon_url = url_for('quiz.marathon_mode')
    hardcore_url = url_for('quiz.hardcore_mode_select')
    review_url = url_for('review.review_mode')
    return render_template('index.html', marathon_url=marathon_url, hardcore_url=hardcore_url, review_url=review_url)