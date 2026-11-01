-- ============================================================
-- SoundRack — esquema e dados iniciais (SQLite, SQL puro)
-- Executado automaticamente por db.py quando a base não existe.
-- Para recriar do zero:  python db.py --reset
-- ============================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS item_tracks;
DROP TABLE IF EXISTS tracks;
DROP TABLE IF EXISTS items;

-- ------------------------------------------------------------
-- items: uma linha por ficheiro de imagem em assets/clothes/
-- file_stem = nome do ficheiro SEM extensão, grafia exata
-- (espaços, acentos e underscores incluídos). O backend descobre
-- a extensão real (.png, .jpg, .webp...) lendo a pasta.
-- ------------------------------------------------------------
CREATE TABLE items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT    NOT NULL UNIQUE,
    file_stem   TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    brand       TEXT    NOT NULL,
    style       TEXT    NOT NULL CHECK (style IN ('Trap', 'Rock', 'Streetwear')),
    category    TEXT    NOT NULL,
    details     TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- tracks: músicas/artistas usados na pesquisa do Spotify.
-- title pode ser NULL (então busca-se a faixa mais popular do artista).
-- spotify_id é opcional: se preenchido, fixa a faixa exata.
-- ------------------------------------------------------------
CREATE TABLE tracks (
    id          INTEGER PRIMARY KEY,
    title       TEXT,
    artist      TEXT NOT NULL,
    album       TEXT,
    spotify_id  TEXT
);

-- ------------------------------------------------------------
-- item_tracks: relação N:N entre peças e faixas
-- ------------------------------------------------------------
CREATE TABLE item_tracks (
    item_id     INTEGER NOT NULL REFERENCES items(id)  ON DELETE CASCADE,
    track_id    INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 1,
    is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    PRIMARY KEY (item_id, track_id)
);

CREATE INDEX idx_items_style        ON items(style);
CREATE INDEX idx_item_tracks_track  ON item_tracks(track_id);
-- no máximo uma faixa principal por peça
CREATE UNIQUE INDEX uq_item_primary ON item_tracks(item_id) WHERE is_primary = 1;

-- ============================================================
-- DADOS: peças (16 ficheiros, grafia exata)
-- ============================================================
INSERT INTO items (id, slug, file_stem, name, brand, style, category, details, sort_order) VALUES
(1,  'calca-1',          'calça 1',          'Calça Baggy 01',           'SoundRack Archive', 'Streetwear', 'Calça',
     'Modelagem ampla de inspiração skate/hip-hop, caimento solto e cintura baixa. Peça-base de qualquer look streetwear.', 1),
(2,  'calca-2',          'calça 2',          'Calça Baggy 02',           'SoundRack Archive', 'Trap',       'Calça',
     'Perna larga e barra volumosa, pensada para combinar com puffers e tênis grossos. Visual de palco e de rua.', 2),
(3,  'calca-3',          'calça 3',          'Calça Baggy 03',           'SoundRack Archive', 'Streetwear', 'Calça',
     'Silhueta relaxada com atitude urbana. Boa para sobreposições e looks monocromáticos.', 3),
(4,  'calca-cargo-3',    'calça cargo 3',    'Calça Cargo 03',           'SoundRack Archive', 'Trap',       'Calça',
     'Cargo utilitária com bolsos laterais e corte largo. Segunda variação da linha cargo.', 4),
(5,  'calca-cargo',      'calça cargo',      'Calça Cargo Clássica',     'SoundRack Archive', 'Trap',       'Calça',
     'A cargo original da arara: bolsos de volume, tecido resistente e estética de rua pesada.', 5),
(6,  'jaqueta-de-couro', 'jaqueta de couro', 'Jaqueta de Couro',         'SoundRack Archive', 'Rock',       'Jaqueta',
     'Clássico biker em couro, gola marcada e ar de show de rock dos anos 70/80.', 6),
(7,  'jaqueta',          'jaqueta',          'Jaqueta Rocker',           'SoundRack Archive', 'Rock',       'Jaqueta',
     'Jaqueta de corte reto, versátil e com pegada de banda de garagem.', 7),
(8,  'marty-supreme-black-jacket', 'marty supreme black jacket', 'Marty Supreme Black Jacket', 'Marty Supreme', 'Streetwear', 'Jaqueta',
     'Jaqueta preta inspirada no universo Marty Supreme: visual esportivo-retrô com atitude de hustler.', 8),
(9,  'puffer-travis',    'puffer_travis',    'Puffer Travis',            'Cactus Jack',       'Trap',       'Puffer',
     'Puffer volumosa inspirada na estética Cactus Jack / Travis Scott. Silhueta inflada e presença de palco.', 9),
(10, 't-shirt-2',        't shirt 2',        'Camiseta 02',              'SoundRack Archive', 'Rock',       'Camiseta',
     'Camiseta oversized de estampa gráfica, pegada de merch de turnê.', 10),
(11, 't-shirt-5',        't shirt 5',        'Camiseta 05',              'SoundRack Archive', 'Rock',       'Camiseta',
     'Camiseta de algodão com visual desbotado de banda clássica.', 11),
(12, 't-shirt-6',        't shirt 6',        'Camiseta 06',              'SoundRack Archive', 'Trap',       'Camiseta',
     'Camiseta larga de estampa gráfica, boa para compor com calça cargo e corrente.', 12),
(13, 't-shirt-8',        't shirt 8',        'Camiseta 08',              'SoundRack Archive', 'Rock',       'Camiseta',
     'Camiseta preta de visual alternativo, inspirada em capas de álbum.', 13),
(14, 't-shirt-9',        't shirt 9',        'Camiseta 09',              'SoundRack Archive', 'Streetwear', 'Camiseta',
     'Camiseta básica de caimento boxy, peça coringa do guarda-roupa urbano.', 14),
(15, 't-shirt-10',       't shirt 10',       'Camiseta 10',              'SoundRack Archive', 'Trap',       'Camiseta',
     'Camiseta oversized com estampa de impacto, estilo rapper de palco.', 15),
(16, 't-shirt-fight-club','t shirt fight club','Camiseta Fight Club',    'Fight Club',        'Rock',       'Camiseta',
     'Camiseta inspirada em Fight Club: estética punk-contracultural e gráfico de cinema cult.', 16);

-- ============================================================
-- DADOS: faixas (título, artista, álbum)
-- ============================================================
INSERT INTO tracks (id, title, artist, album) VALUES
(1,  'SICKO MODE',                'Travis Scott',      'ASTROWORLD'),
(2,  'Hotline Bling',             'Drake',             'Views'),
(3,  'HUMBLE.',                   'Kendrick Lamar',    'DAMN.'),
(4,  'DNA.',                      'Kendrick Lamar',    'DAMN.'),
(5,  'Castelos & Ruínas',         'BK',                'Castelos & Ruínas'),
(6,  'Quer Voar',                 'Matuê',             NULL),
(7,  NULL,                        '2ZDinizz',          NULL),
(8,  '777-666',                   'Matuê',             NULL),
(9,  'Sweet Child O'' Mine',      'Guns N'' Roses',    'Appetite for Destruction'),
(10, 'Blitzkrieg Bop',            'Ramones',           'Ramones'),
(11, 'Californication',           'Red Hot Chili Peppers', 'Californication'),
(12, 'Reptilia',                  'The Strokes',       'Room on Fire'),
(13, 'Started From the Bottom',   'Drake',             'Nothing Was the Same'),
(14, 'goosebumps',                'Travis Scott',      'Birds in the Trap Sing McKnight'),
(15, 'FE!N',                      'Travis Scott',      'UTOPIA'),
(16, 'HIGHEST IN THE ROOM',       'Travis Scott',      NULL),
(17, 'Smells Like Teen Spirit',   'Nirvana',           'Nevermind'),
(18, 'Paranoid',                  'Black Sabbath',     'Paranoid'),
(19, 'Money Trees',               'Kendrick Lamar',    'good kid, m.A.A.d city'),
(20, 'In the End',                'Linkin Park',       'Hybrid Theory'),
(21, 'God''s Plan',               'Drake',             'Scary Hours'),
(22, 'Anos Luz',                  'Matuê',             NULL),
(23, 'Where Is My Mind?',         'Pixies',            'Surfer Rosa'),
(24, 'Come as You Are',           'Nirvana',           'Nevermind'),
(25, 'Iron Man',                  'Black Sabbath',     'Paranoid'),
(26, 'Alright',                   'Kendrick Lamar',    'To Pimp a Butterfly'),
(27, 'Numb',                      'Linkin Park',       'Meteora'),
(28, 'One Dance',                 'Drake',             'Views'),
(29, 'Máquina do Tempo',          'Matuê',             'Máquina do Tempo'),
(30, 'Debaser',                   'Pixies',            'Doolittle');

-- ============================================================
-- DADOS: relação peça <-> faixa (a primeira de cada peça é a principal)
-- ============================================================
INSERT INTO item_tracks (item_id, track_id, position, is_primary)
SELECT i.id, v.track_id, v.position, v.is_primary
FROM (
    SELECT 'calça 1'            AS stem,  1 AS track_id, 1 AS position, 1 AS is_primary UNION ALL
    SELECT 'calça 1',                     2,             2,             0 UNION ALL
    SELECT 'calça 2',                     3,             1,             1 UNION ALL
    SELECT 'calça 2',                     4,             2,             0 UNION ALL
    SELECT 'calça 3',                     5,             1,             1 UNION ALL
    SELECT 'calça 3',                    28,             2,             0 UNION ALL
    SELECT 'calça cargo 3',               6,             1,             1 UNION ALL
    SELECT 'calça cargo 3',               8,             2,             0 UNION ALL
    SELECT 'calça cargo',                 7,             1,             1 UNION ALL
    SELECT 'calça cargo',                22,             2,             0 UNION ALL
    SELECT 'jaqueta de couro',            9,             1,             1 UNION ALL
    SELECT 'jaqueta de couro',           10,             2,             0 UNION ALL
    SELECT 'jaqueta',                    11,             1,             1 UNION ALL
    SELECT 'jaqueta',                    12,             2,             0 UNION ALL
    SELECT 'marty supreme black jacket', 13,             1,             1 UNION ALL
    SELECT 'marty supreme black jacket', 14,             2,             0 UNION ALL
    SELECT 'puffer_travis',              15,             1,             1 UNION ALL
    SELECT 'puffer_travis',              16,             2,             0 UNION ALL
    SELECT 't shirt 2',                  17,             1,             1 UNION ALL
    SELECT 't shirt 2',                  24,             2,             0 UNION ALL
    SELECT 't shirt 5',                  18,             1,             1 UNION ALL
    SELECT 't shirt 5',                  25,             2,             0 UNION ALL
    SELECT 't shirt 6',                  19,             1,             1 UNION ALL
    SELECT 't shirt 6',                  26,             2,             0 UNION ALL
    SELECT 't shirt 8',                  20,             1,             1 UNION ALL
    SELECT 't shirt 8',                  27,             2,             0 UNION ALL
    SELECT 't shirt 9',                  21,             1,             1 UNION ALL
    SELECT 't shirt 9',                   2,             2,             0 UNION ALL
    SELECT 't shirt 10',                 29,             1,             1 UNION ALL
    SELECT 't shirt 10',                  4,             2,             0 UNION ALL
    SELECT 't shirt fight club',         23,             1,             1 UNION ALL
    SELECT 't shirt fight club',         30,             2,             0
) AS v
JOIN items i ON i.file_stem = v.stem;
