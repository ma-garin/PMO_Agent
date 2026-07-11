# インフラはPostgreSQLに一本化する（pgvector + Procrastinate）

DB・ベクトルストア・非同期ジョブキューをすべてPostgreSQLに載せる（2026-07-11決定）: RAGはpgvector、ジョブキューはProcrastinate（PostgresのLISTEN/NOTIFYベース）。Celery+Redisという実績構成をあえて選ばなかったのは、小規模（同時〜10案件・〜20ユーザー）の社内ツールでは追加ミドルウェアの運用コストがスケーラビリティの利益を上回るため。規模が中規模（〜50案件）を超えた時点でキュー基盤の再評価を行う。
