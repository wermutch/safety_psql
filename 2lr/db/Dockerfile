FROM postgres:18

# ru_RU.UTF-8 (Lang = ru_RU.UTF-8).
RUN sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen

ENV LANG=ru_RU.UTF-8
ENV LC_ALL=ru_RU.UTF-8
