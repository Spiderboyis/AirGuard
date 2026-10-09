FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt
COPY common ${LAMBDA_TASK_ROOT}/common
COPY engine ${LAMBDA_TASK_ROOT}/engine
COPY api ${LAMBDA_TASK_ROOT}/api
COPY agent ${LAMBDA_TASK_ROOT}/agent
COPY ingestion ${LAMBDA_TASK_ROOT}/ingestion
COPY ml ${LAMBDA_TASK_ROOT}/ml
CMD ["api.main.handler"]
