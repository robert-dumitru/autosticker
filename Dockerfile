FROM python:3.10-bullseye as builder

# create requirements file from poetry
SHELL ["/bin/bash", "-c"]
COPY poetry.lock pyproject.toml ./
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN ${HOME}/.local/bin/poetry export --output requirements.txt
# create venv and install dependencies to it
RUN python3 -m venv /.venv && source /.venv/bin/activate
RUN pip install -r requirements.txt

FROM python:3.10-bullseye

# copy files from build stage and run
SHELL ["/bin/bash", "-c"]
RUN mkdir -p app
WORKDIR app
ADD app .
COPY --from=builder /.venv .venv/
RUN ls -a
RUN source .venv/bin/activate
CMD [ "python3", "-m", "/app" ]
