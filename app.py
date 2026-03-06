from flask import Flask, render_template
from database import init_db
from modules.legal_scoring import bp as legal_bp
from modules.attorney_placements import bp as placements_bp
from modules.legal_eligibility import bp as eligibility_bp

app = Flask(__name__)
app.secret_key = "pra-legal-recovery-2024"
app.register_blueprint(legal_bp)
app.register_blueprint(placements_bp)
app.register_blueprint(eligibility_bp)


@app.route('/')
def landing():
    return render_template('landing.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
