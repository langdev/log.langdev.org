CREATE TABLE flags (
    id integer primary key autoincrement,
    date string not null,
    line integer not null,
    title string not null,
    user string not null,
    time text
);
