
from flask import Flask

app = Flask(__name__)


@app.route('/')
def home():
    return 'Instagram Auto DM - Sistema funcionando!'


@app.route('/auth/instagram/callback')
def instagram_callback():
    return 'Rota de autenticação do Instagram'


if __name__ == '__main__':
    app.run(debug=True)
