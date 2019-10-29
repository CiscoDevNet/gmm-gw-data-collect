FROM python:alpine

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY kinetic_gmm_collect.py .

RUN mkdir /config

CMD [ "python", "kinetic_gmm_collect.py" ]