import os
import psycopg
from app.db import rag_connection_settings
with psycopg.connect(**rag_connection_settings(),autocommit=True) as connection:
    assert connection.execute('SELECT current_user').fetchone()[0]=='rag_reader'
    for sql in ['SELECT * FROM evaluation.phase4_ground_truth_probe','SELECT * FROM app.requirement',
        'SELECT * FROM app.requirement_analysis','SELECT * FROM app.test_case','SELECT * FROM app.test_case_generation',"UPDATE rag.knowledge_chunk SET content='forbidden' WHERE false"]:
        try:connection.execute(sql)
        except psycopg.errors.InsufficientPrivilege:print('PASS SQLSTATE 42501:',sql,flush=True)
        else:raise AssertionError('Forbidden access succeeded')
    assert connection.execute('SELECT count(*) FROM rag.knowledge_chunk').fetchone()[0]==27
keys=[k for k in os.environ if 'DB' in k or 'EVALUATION' in k]
assert not any('EVALUATION' in k or 'MIGRATION' in k or 'DB_APP' in k for k in keys)
print('PASS runtime role rag_reader; no app/evaluation/migration credentials; 27 chunks')
