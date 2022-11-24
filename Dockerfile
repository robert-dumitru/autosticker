FROM python:3.10-bullseye as builder

# create requirements file from poetry
SHELL ["/bin/bash", "-c"]
COPY poetry.lock pyproject.toml ./
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN ${HOME}/.local/bin/poetry export --output requirements.txt
# create venv and install dependencies to it
ENV VIRTUAL_ENV=/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install -r requirements.txt

FROM python:3.10-bullseye

# copy in secrets
ARG OPENAI_ORG
ARG OPENAI_API_KEY
ARG REPLICATE_API_TOKEN
ARG AUTOSTICKER_TG_TOKEN

# copy files from build stage and run
SHELL ["/bin/bash", "-c"]
RUN mkdir -p app
WORKDIR app
ENV VIRTUAL_ENV=/opt/venv
COPY --from=builder /venv $VIRTUAL_ENV
ADD app .
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /
CMD ["python3", "-m", "app"]
