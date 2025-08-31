# app.py
import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, date
import calendar

from dotenv import load_dotenv
load_dotenv()


# --- CONFIGURAÇÃO DO LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
CORS(app) 

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    logger.error("A variável de ambiente 'DATABASE_URL' não foi encontrada!")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    logger.info("URL do banco de dados configurada com sucesso.")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura'

db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS (Estrutura dos Dados) ---
# Mantenha os modelos QuadroMensal e Conta inalterados

class QuadroMensal(db.Model):
    __tablename__ = 'quadro_mensal'
    id = db.Column(db.Integer, primary_key=True)
    ano = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    salario1 = db.Column(db.Float, default=0.0)
    salario2 = db.Column(db.Float, default=0.0)
    contas = db.relationship('Conta', backref='quadro', lazy=True, cascade="all, delete-orphan")

class Conta(db.Model):
    __tablename__ = 'conta'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    fonte_pagamento = db.Column(db.Integer, nullable=False)
    quadro_id = db.Column(db.Integer, db.ForeignKey('quadro_mensal.id'), nullable=False)

def calcular_semanas_mes(ano, mes):
    cal = calendar.monthcalendar(ano, mes)
    semanas = []
    for i, semana in enumerate(cal):
        dias_semana = [dia for dia in semana if dia != 0]
        if dias_semana:
            semanas.append({
                'numero': i + 1,
                'dias': dias_semana,
                'primeiro_dia': min(dias_semana),
                'ultimo_dia': max(dias_semana)
            })
    return semanas

def calcular_dinheiro_semana(quadro, semanas):
    resultado_semanas = []
    saldo_acumulado = 0.0
    for semana in semanas:
        dinheiro_inicial = 0.0
        if semana['primeiro_dia'] <= 5 <= semana['ultimo_dia']:
            dinheiro_inicial += quadro['salario1']
        if semana['primeiro_dia'] <= 20 <= semana['ultimo_dia']:
            dinheiro_inicial += quadro['salario2']
        dinheiro_inicial += saldo_acumulado
        contas_semana = [c for c in quadro['contas'] if semana['primeiro_dia'] <= datetime.fromisoformat(c['data_vencimento']).day <= semana['ultimo_dia']]
        total_contas = sum(c['valor'] for c in contas_semana)
        dinheiro_restante = dinheiro_inicial - total_contas
        if dinheiro_restante < 0:
            saldo_acumulado = dinheiro_restante
            dinheiro_restante = 0.0
        else:
            saldo_acumulado = dinheiro_restante
        resultado_semanas.append({
            'numero': semana['numero'],
            'dias': semana['dias'],
            'dinheiro_inicial': dinheiro_inicial,
            'contas': contas_semana,
            'total_contas': total_contas,
            'dinheiro_restante': dinheiro_restante,
            'saldo_acumulado': saldo_acumulado
        })
    return resultado_semanas

@app.route('/api/quadros')
def get_quadros():
    todos_quadros = QuadroMensal.query.order_by(QuadroMensal.ano.desc(), QuadroMensal.mes.desc()).all()
    lista_quadros = [{'id': q.id, 'ano': q.ano, 'mes': q.mes} for q in todos_quadros]
    return jsonify(lista_quadros)

@app.route('/api/quadros/<int:quadro_id>')
def get_quadro(quadro_id):
    quadro = QuadroMensal.query.get_or_404(quadro_id)
    
    todas_as_contas = Conta.query.filter_by(quadro_id=quadro.id).order_by(Conta.data_vencimento).all()
    
    contas_convertidas = [{
        'id': c.id, 
        'descricao': c.descricao, 
        'valor': c.valor, 
        'data_vencimento': c.data_vencimento.isoformat(),
        'fonte_pagamento': c.fonte_pagamento
    } for c in todas_as_contas]

    contas_salario1 = [c for c in contas_convertidas if c['fonte_pagamento'] == 1]
    contas_salario2 = [c for c in contas_convertidas if c['fonte_pagamento'] == 2]
    
    gasto_salario1 = sum(c['valor'] for c in contas_salario1)
    gasto_salario2 = sum(c['valor'] for c in contas_salario2)
    
    quadro_data = {
        'id': quadro.id, 
        'ano': quadro.ano, 
        'mes': quadro.mes, 
        'salario1': quadro.salario1, 
        'salario2': quadro.salario2,
        'contas': contas_convertidas
    }
    
    semanas = calcular_semanas_mes(quadro.ano, quadro.mes)
    semanas_dinheiro = calcular_dinheiro_semana(quadro_data, semanas)

    return jsonify({
        'quadro': quadro_data,
        'resumo_saldos': {
            'gasto1': gasto_salario1, 'saldo1': quadro.salario1 - gasto_salario1,
            'gasto2': gasto_salario2, 'saldo2': quadro.salario2 - gasto_salario2,
        },
        'contas': {
            'salario1': contas_salario1,
            'salario2': contas_salario2,
        },
        'resumo_semanal': semanas_dinheiro
    })

@app.route('/api/quadros', methods=['POST'])
def criar_quadro():
    data = request.get_json()
    ano = data.get('ano')
    mes = data.get('mes')
    existente = QuadroMensal.query.filter_by(ano=ano, mes=mes).first()
    if existente:
        return jsonify({'message': 'Quadro já existe.', 'quadro_id': existente.id}), 409
    novo_quadro = QuadroMensal(ano=ano, mes=mes)
    db.session.add(novo_quadro)
    db.session.commit()
    return jsonify({'message': 'Quadro criado com sucesso!', 'quadro_id': novo_quadro.id}), 201

@app.route('/api/quadros/<int:quadro_id>/salarios', methods=['PUT'])
def definir_salarios(quadro_id):
    quadro = QuadroMensal.query.get_or_404(quadro_id)
    data = request.get_json()
    try:
        quadro.salario1 = float(data.get('salario1'))
        quadro.salario2 = float(data.get('salario2'))
        db.session.commit()
        return jsonify({'message': 'Salários atualizados com sucesso!'}), 200
    except (ValueError, TypeError):
        return jsonify({'message': 'Valores de salário inválidos.'}), 400

@app.route('/api/contas', methods=['POST'])
def adicionar_conta():
    data = request.get_json()
    try:
        nova_conta = Conta(
            descricao=data.get('descricao'),
            valor=float(data.get('valor')),
            data_vencimento=datetime.strptime(data.get('data_vencimento'), '%Y-%m-%d').date(),
            fonte_pagamento=int(data.get('fonte_pagamento')),
            quadro_id=int(data.get('quadro_id'))
        )
        db.session.add(nova_conta)
        db.session.commit()
        return jsonify({'message': 'Conta adicionada com sucesso!', 'id': nova_conta.id}), 201
    except (ValueError, TypeError):
        return jsonify({'message': 'Dados da conta inválidos.'}), 400

@app.route('/api/contas/<int:conta_id>', methods=['PUT'])
def editar_conta(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    data = request.get_json()
    try:
        if 'valor' in data:
            conta.valor = float(data.get('valor'))
        if 'data_vencimento' in data:
            conta.data_vencimento = datetime.strptime(data.get('data_vencimento'), '%Y-%m-%d').date()
        if 'descricao' in data:
            conta.descricao = data.get('descricao')
        db.session.commit()
        return jsonify({'message': 'Conta editada com sucesso!'}), 200
    except (ValueError, TypeError):
        return jsonify({'message': 'Valor ou data inválidos.'}), 400

@app.route('/api/contas/<int:conta_id>', methods=['DELETE'])
def excluir_conta(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    db.session.delete(conta)
    db.session.commit()
    return jsonify({'message': 'Conta excluída com sucesso!'}), 200

# --- INICIALIZAÇÃO ---
if __name__ == '__main__':
    with app.app_context():
        try:
            # Tenta fazer uma consulta simples para verificar a conexão
            db.session.execute(db.select(QuadroMensal).limit(1))
            logger.info("Conexão com o banco de dados Supabase bem-sucedida.")
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco de dados Supabase: {e}")
            # Em caso de erro de conexão, a aplicação não deve rodar
            exit(1)
    app.run(debug=True,host="0.0.0.0")