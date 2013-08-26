CREATE TABLE flags (
    id integer primary key autoincrement,
    channel string not null,
    date string not null,
    line integer not null,
    title string not null,
    user string not null,
    time text
);
