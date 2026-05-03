-- Restore backup for embedding_labels
BEGIN;

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (0, 'Action-Oriented Sports Dramas', '2026-03-03T11:31:42.514723'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1, 'Historical Romance Dramas', '2026-03-03T07:40:29.191421'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (2, 'Feature films over TV episodes', '2026-05-02T07:31:53.130417'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (3, 'Music Concert Experiences', '2026-03-03T05:12:46.419842'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (4, 'Dark Crime Action Dramas', '2026-03-03T05:13:30.802627'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (5, 'Historical Music Documentaries & Concerts', '2026-03-03T08:01:40.495792'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (6, 'Sports Dramas with Historical Context', '2026-03-03T05:03:14.873254'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (7, 'Character-Driven Dramas', '2026-03-03T00:12:45.830842'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (8, 'Dark Comedies, Crime Thrillers', '2026-03-03T11:23:18.472716'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (9, 'High‑profile star‑driven mainstream blockbusters', '2026-04-30T07:39:25.896724'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (10, 'Historical Romance Dramas', '2026-03-03T07:50:07.101504'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (11, 'Historical Dramas with Strong Male Leads', '2026-03-03T09:57:55.678199'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (12, 'Romantic Musicals & Historical Dramas', '2026-03-03T10:07:58.991903'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (13, 'Romantic Period Dramas', '2026-03-03T10:56:00.684499'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (14, 'Romantic Dramas with Historical Settings', '2026-03-03T10:46:14.692927'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (15, 'Musical Concert Films', '2026-03-03T08:26:31.785493'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (16, 'Recent drama‑heavy TV episodes', '2026-05-02T07:53:08.760264'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (17, 'Action-Oriented Crime Dramas', '2026-03-03T08:20:40.747188'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (18, 'Musical Biographies & Historical Dramas', '2026-03-03T10:05:16.028751'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (19, 'Franchise-Driven Family Entertainment', '2026-03-03T10:39:11.600511'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (20, 'Niche subcultural settings over mainstream spectacle', '2026-05-02T07:55:46.067855'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (21, 'Prestige drama & literary adaptations', '2026-05-01T08:28:31.949069'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (22, 'Romantic Period Dramas', '2026-03-02T11:51:03.564203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (23, 'Action Comedy Franchises', '2026-03-03T10:35:16.139288'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (24, 'Drama‑centric, mystery/romance‑heavy titles', '2026-05-02T07:45:20.583976'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (25, 'Historical Music Biographies', '2026-03-03T07:53:38.073522'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (26, 'Likes gritty crime/action, dislikes mellow drama/romance', '2026-04-27T10:59:29.936211'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (27, 'Romantic Musicals & Comedies', '2026-03-03T00:04:05.374961'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (28, 'Action-Crime Dramas with Strong Leads', '2026-03-02T11:51:26.447380'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (29, 'Musical Performance Focus', '2026-03-03T10:41:32.804223'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (30, 'High‑stakes conflict‑driven narratives', '2026-04-30T07:48:46.311840'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (31, 'Music biopics about artists'' early lives', '2026-04-30T07:40:44.662299'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (32, 'Action/Crime thrillers vs Romance/Drama', '2026-05-02T07:36:56.958101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (33, 'Crime Dramas with Strong Male Leads', '2026-03-03T10:26:10.366490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (34, 'Western-Inspired Crime Dramas', '2026-03-03T05:00:31.907860'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (35, 'Preference for drama‑centric stories', '2026-03-06T04:40:19.703102'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (36, 'Romantic Comedies with Strong Female Leads', '2026-03-02T12:16:19.854457'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (37, 'Romantic Musicals with Ensemble Casts', '2026-03-03T00:24:15.596751'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (38, 'Musicals & Concert Films Preferred', '2026-03-02T12:07:40.989647'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (39, 'Action-Comedy Franchise Focus', '2026-03-05T05:08:26.622890'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (40, 'High‑concept genre cinema over realistic drama/TV', '2026-05-02T07:57:13.635079'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (41, 'Grounded drama and dramedy over high‑concept genre spectacles', '2026-05-02T07:55:24.190411'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (42, 'Adaptations of existing works (books, music, TV)', '2026-05-02T07:44:07.236604'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (43, 'Short‑form romance/drama episodes over feature‑length action', '2026-05-02T07:40:34.710464'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (44, 'Sport-Driven Dramatic Rivalries', '2026-03-03T10:21:14.046713'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (45, 'High-Budget Action Dramas', '2026-03-03T10:37:15.183341'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (46, 'Historical Music Dramas', '2026-03-03T08:42:26.222178'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (47, 'Action‑Adventure/Comedy Blockbuster Preference', '2026-04-27T10:58:24.657753'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (48, 'Musical Variety Entertainment', '2026-03-03T11:01:06.332428'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (49, 'Prefers episodic/short-form content', '2026-04-27T01:26:48.370055'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (50, 'Historical Romance Dramas', '2026-03-03T11:12:15.748544'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (51, 'Action-Oriented Crime Dramas', '2026-03-02T23:28:11.392255'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (52, 'Musicals and Concert Films', '2026-03-03T08:20:14.742456'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (53, 'Feature‑film narrative preference', '2026-04-30T07:43:10.492856'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (54, 'Preference for drama‑tagged titles', '2026-04-29T17:24:07.146595'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (55, 'Musical Biographies & Concert Films', '2026-03-03T07:48:59.255244'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (56, 'Preference for female‑lead titles', '2026-05-02T07:33:46.858673'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (57, 'Historical Period Pieces', '2026-03-03T05:04:01.628859'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (58, 'Musical Biopics & Concert Films', '2026-03-03T10:48:10.105450'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (59, 'High-Budget Music & Drama', '2026-03-04T05:15:12.773604'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (60, 'Action Comedies with Strong Leads', '2026-03-03T07:37:46.203436'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (61, 'High‑stakes competition and survival dramas', '2026-04-27T11:00:17.146361'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (62, 'Historical Romance Dramas', '2026-03-03T08:00:52.704924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (63, 'Romantic Comedy Family Films', '2026-03-03T11:35:09.530490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (64, 'Preference for colon‑subtitle titles', '2026-03-06T01:19:34.371894'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (65, 'Historical Romance Dramas', '2026-03-03T07:41:39.807636'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (66, 'Serious adult drama (crime/sport/biography)', '2026-04-28T11:07:06.565918'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (67, 'High-Octane Action Franchises', '2026-03-03T08:16:46.549220'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (68, 'Romantic Comedies & Family Films', '2026-03-03T08:41:37.815277'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (69, 'Music‑centric drama and biography', '2026-04-29T07:56:52.375596'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (70, 'Action-Comedy Franchises', '2026-03-03T04:58:02.162089'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (71, 'Preference for drama/romance, not action/comedy', '2026-05-02T07:37:07.075861'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (72, 'Music Documentaries & Concert Films', '2026-03-03T04:54:06.154393'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (73, 'Prefers movies over TV episodes', '2026-04-27T11:11:59.571874'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (74, 'Action-Oriented Genre Blends', '2026-03-03T10:04:53.986876'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (75, 'Action‑driven blockbusters vs drama‑focused titles', '2026-05-02T07:37:33.641016'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (76, 'Action‑Crime/Adventure with Comedy mix', '2026-05-02T07:46:07.337930'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (77, 'Neil Diamond Tribute Acts', '2026-03-03T10:20:24.802259'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (78, 'Preference for contemporary narratives over period/documentary', '2026-04-27T01:30:56.391641'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (79, 'Action Thrillers with Strong Male Leads', '2026-03-03T10:28:06.320823'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (80, 'Dark Comedy Family Focus', '2026-03-02T12:19:31.469302'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (81, 'Historical Romance Dramas', '2026-03-03T08:17:09.342178'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (82, 'Historical Romance Dramas', '2026-03-05T04:49:31.713292'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (83, 'Historical Romance Dramas', '2026-03-03T00:05:35.850505'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (84, '90s Rom-Coms with Strong Female Leads', '2026-03-03T04:56:01.400365'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (85, 'Prefers feature‑length movies over TV episodes', '2026-04-29T09:49:33.074721'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (86, 'Historical Romance Musical Dramas', '2026-03-03T05:09:14.635845'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (87, 'Big Budget Action Comedies', '2026-03-03T07:26:49.132382'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (88, 'Loves genre‑blending, plot‑driven fiction', '2026-05-01T08:33:01.364174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (89, 'Crime/Thriller fan vs music documentary fan', '2026-04-28T11:04:52.676637'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (90, 'Historical Romance Dramas', '2026-03-03T08:15:13.666291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (91, 'Animated Family Comedies', '2026-03-03T09:50:43.934516'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (92, 'Contemporary pop music docs & comedy-action mix', '2026-04-29T09:46:55.107026'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (93, 'High-Octane Action Dramas', '2026-03-03T00:15:04.973469'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (94, 'Preference for character-driven drama over action‑heavy fare', '2026-04-29T09:50:35.447764'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (95, 'Action Thrillers with Strong Leads', '2026-03-03T00:27:19.142979'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (96, 'Drama‑heavy multi‑genre titles', '2026-05-02T07:51:58.895357'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (97, 'Genre‑driven movies & comedy series vs prestige dramas', '2026-04-30T07:46:24.080712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (98, 'Biopic & literary drama lovers', '2026-05-01T08:26:59.326569'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (99, 'Fast‑paced Action/Crime‑Comedy Preference', '2026-05-01T08:36:41.524530'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (100, 'Historical Period Pieces', '2026-03-03T07:44:23.887176'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (101, 'Romantic Musicals & Concert Films', '2026-03-03T10:10:12.706887'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (102, 'Historical Romance Dramas', '2026-03-03T10:13:39.728629'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (103, 'Contemporary non‑musical narrative dramas', '2026-05-01T08:27:11.040527'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (104, 'Pop‑culture celebrity & action vs prestige drama', '2026-05-02T07:40:52.803397'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (105, 'Romantic Musicals with Historical Settings', '2026-03-03T11:01:29.604391'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (106, 'Prefers long-form dramatic/action movies over short TV episodes', '2026-05-02T07:43:18.685381'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (107, 'Historical Dramas with Strong Male Leads', '2026-03-03T09:58:41.085771'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (108, 'Romantic Musicals & Concert Films', '2026-03-03T11:22:55.354701'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (109, 'Action Comedies with Strong Leads', '2026-03-03T07:52:27.583949'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (110, 'Historical Sports Dramas', '2026-03-03T04:59:18.794878'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (111, 'Romantic Period Dramas', '2026-03-03T10:25:01.878200'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (112, 'Musical Concert Experiences', '2026-03-03T00:19:17.856609'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (113, 'Historical Romance Dramas', '2026-03-03T04:40:40.909566'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (114, 'Prefers action‑crime thrillers over character dramas', '2026-04-29T07:53:23.777015'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (115, 'Animated Family Comedies', '2026-03-03T11:08:02.539745'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (116, 'Adult drama and biopic preference', '2026-05-02T07:40:02.650023'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (117, 'Prefers high‑rated scripted dramas over documentaries/period romances', '2026-04-29T17:30:33.386744'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (118, 'Romantic Period Dramas', '2026-03-03T08:08:42.081062'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (119, 'Preference for high‑energy, genre‑blending pop‑culture titles', '2026-05-02T07:41:50.408523'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (120, 'Genre-Driven Sport & Action Preferences', '2026-03-05T05:06:16.227605'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (121, 'Romantic Period Dramas', '2026-03-03T10:29:13.254400'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (122, 'Family-Friendly Animated Comedies', '2026-03-03T11:04:58.444769'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (123, 'Drama‑focused genre‑blend indie titles', '2026-04-29T17:19:14.218948'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (124, 'Drama‑focused historical and romance narratives', '2026-05-01T08:38:51.733561'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (125, 'Historical Dramas with Strong Performances', '2026-03-03T10:27:19.848642'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (126, 'Pop‑culture‑focused titles (music docs, food comedy, modern crime)', '2026-04-29T08:06:11.791732'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (127, '{', '2026-03-03T09:49:58.815885'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (128, 'Musical Concert Films', '2026-03-04T04:57:18.040583'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (129, 'Musical Concert Experiences', '2026-03-03T10:24:39.205335'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (130, 'Prefers narrative biopics and dramas over concert films', '2026-04-30T07:41:09.157478'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (131, 'Crime Thrillers with Strong Leads', '2026-03-03T07:27:10.956637'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (132, 'Musical Performance Preference', '2026-03-03T08:21:02.925646'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (133, 'Musical Concert Films Dominate', '2026-03-03T10:38:26.181612'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (134, 'Action-Comedy Franchises', '2026-03-02T12:01:49.636660'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (135, 'Musicals & Concert Films', '2026-03-03T08:27:41.020092'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (136, 'Fictional narrative titles vs documentaries/biopics', '2026-05-01T08:25:33.532709'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (137, 'Competition & scheming over romance‑drama', '2026-04-28T11:03:41.085231'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (138, 'Musicals & Concert Films', '2026-03-02T12:03:00.138404'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (139, 'Prefers TV episodes over feature films', '2026-05-02T07:40:17.637889'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (140, 'Preference for recent feature films over TV episodes', '2026-05-02T07:33:02.937875'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (141, 'Western Crime Dramas', '2026-03-03T10:02:32.299085'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (142, 'Musical Era Focus', '2026-03-05T05:13:24.819207'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (143, 'Drama with crime, mystery, or comedy', '2026-05-02T07:56:36.923729'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (144, 'Preference for crime/mystery/thriller content', '2026-04-27T10:50:34.567325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (145, 'Professional/skill‑centric narratives', '2026-04-27T11:12:34.036911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (146, 'High‑energy, genre‑blended feature films', '2026-05-02T07:35:10.500738'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (147, 'Romance‑focused titles', '2026-04-29T17:22:46.965497'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (148, 'Dark Comedies, Action-Oriented', '2026-03-03T00:03:42.442515'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (149, 'Artistic/creative‑themed titles', '2026-05-02T07:50:42.337765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (150, 'Performance & competition‑centric titles', '2026-04-29T10:00:30.165588'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (151, 'Romantic Musicals & Concert Films', '2026-03-03T09:44:38.417858'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (152, 'Western Crime Dramas', '2026-03-03T11:18:43.757009'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (153, 'Music-Driven Historical Dramas', '2026-03-03T10:18:51.624380'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (154, 'Sport-Driven Dramas with Intense Rivalries', '2026-03-03T05:07:43.446167'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (155, 'Musical Biopics & Historical Dramas', '2026-03-03T10:55:38.246661'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (156, '{', '2026-03-02T12:13:05.694278'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (157, 'Action Comedies with Strong Leads', '2026-03-03T07:35:50.658898'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (158, 'Character-Driven Action Dramas', '2026-03-03T07:45:09.833339'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (159, 'Comedy‑driven, music‑flavored titles', '2026-05-02T07:34:18.569834'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (160, 'Romantic Period Dramas', '2026-03-03T09:57:08.769983'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (161, 'Musical Concert Films Dominate', '2026-03-04T05:16:58.301523'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (162, 'Music‑centric drama preference over action', '2026-04-30T07:36:54.311668'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (163, 'High‑stakes competition over personal romance', '2026-04-27T11:09:10.704473'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (164, 'Action-Comedy Crime Franchises', '2026-03-02T12:11:54.996932'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (165, 'Musical Concert Experiences', '2026-03-02T11:55:13.931427'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (166, 'Historical Drama with Ensemble Casts', '2026-03-03T11:04:35.546233'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (167, 'Contemporary TV dramedy episodes vs mainstream movies', '2026-04-30T07:37:41.333344'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (168, 'Historical Dramas with Strong Male Leads', '2026-03-03T10:05:39.220448'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (169, 'Historical Music Romance Dramas', '2026-03-03T00:16:58.849386'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (170, 'Movie‑length films vs TV episodes', '2026-05-01T08:34:35.911466'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (171, 'Musical Concert Films', '2026-03-03T11:26:41.810363'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (172, 'Drama‑centric narratives over high‑octane action', '2026-04-29T08:05:38.180016'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (173, 'Action‑Crime Thrillers and Dark Comedy', '2026-05-02T07:42:16.164837'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (174, 'Dark Comedies & Food Dramas', '2026-03-03T10:58:46.497177'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (175, 'Action‑heavy high‑stakes conflict', '2026-05-02T07:42:55.456846'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (176, 'Character‑driven drama and literary adaptations', '2026-04-28T10:55:43.505297'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (177, 'Musical Concert Experiences', '2026-03-03T04:55:14.545552'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (178, 'Action-Oriented, Fast-Paced Stories', '2026-03-03T00:24:38.403813'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (179, 'Preference for romance‑focused drama titles', '2026-05-02T07:42:06.731904'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (180, 'Prefers action/comedy, avoids romance-focused titles', '2026-05-02T07:50:09.209650'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (181, 'Historical Romance Dramas', '2026-03-03T08:27:18.951134'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (182, 'Drama‑centric narratives vs action/ music documentaries', '2026-04-29T09:58:46.832923'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (183, 'Franchise-Driven Family Entertainment', '2026-03-03T10:02:07.574117'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (184, '90s Rom-Com Revival', '2026-03-03T09:50:21.861926'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (185, 'Action-Comedy Franchise Focus', '2026-03-03T07:39:20.106442'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (186, 'Comedy‑driven action and adventure', '2026-04-27T11:06:08.139823'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (187, 'Crime Thrillers with Strong Female Leads', '2026-03-03T10:28:28.667939'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (188, 'Sport-Focused Dramas & Comedies', '2026-03-03T10:01:45.202096'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (189, 'Musical Concert Films Predominate', '2026-03-03T07:30:58.263104'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (190, 'Franchise-Driven Action Comedies', '2026-03-03T07:28:17.756821'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (191, 'Musical Romance Dramas', '2026-03-03T10:00:37.397394'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (192, 'Romantic Dramas with Strong Female Leads', '2026-03-03T05:00:55.403765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (193, 'Action-Comedy Crime Franchises', '2026-03-03T08:23:43.759268'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (194, 'Prefers movies over TV episodes', '2026-04-29T17:28:52.020606'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (195, 'TV drama with crime/mystery elements', '2026-05-01T08:25:42.002788'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (196, 'Historical Music Dramas', '2026-03-03T11:17:34.426286'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (197, 'Prefers feature‑length movies over TV episodes', '2026-04-28T11:00:25.628260'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (198, 'Action Crime Thrillers', '2026-03-02T12:12:41.159453'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (199, 'Romantic Period Dramas', '2026-03-03T07:32:31.825567'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (200, 'Character-Driven Crime Dramas', '2026-03-03T11:17:10.830107'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (201, 'Action Thrillers with Strong Leads', '2026-03-03T09:51:07.437686'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (202, 'Prefers feature films over TV episodes', '2026-04-29T07:52:14.855176'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (203, '{', '2026-03-03T07:56:59.960500'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (204, 'Historical Dramas with Strong Male Leads', '2026-03-03T11:34:23.176197'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (205, 'Musicals & Concert Films', '2026-03-03T07:51:41.773332'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (206, 'High‑energy spectacle and concert documentary preference', '2026-05-01T08:25:09.661839'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (207, 'Ambition‑driven scripted dramas', '2026-04-27T11:07:56.841628'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (208, 'Action-Comedy Franchises', '2026-03-03T10:38:02.217273'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (209, 'Celebrity‑driven blockbuster and star‑focused content', '2026-05-01T08:38:23.778302'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (210, 'Romantic Dramas with Historical Settings', '2026-03-03T00:06:20.896605'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (211, 'Historical Romance Dramas', '2026-03-03T04:41:46.173153'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (212, 'Action-Oriented Crime Dramas', '2026-03-03T00:05:58.979312'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (213, 'Preference for feature-length movies over TV episodes', '2026-04-27T10:54:01.910124'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (214, 'Crime‑driven action/thriller preference', '2026-05-01T08:33:58.008731'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (215, 'Fictional narrative storytelling over real-world documentary', '2026-04-28T11:03:07.540225'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (216, 'Romantic Dramas with Historical Settings', '2026-03-03T10:47:47.408890'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (217, 'Musicals & Concert Films Preferred', '2026-03-03T07:48:35.107945'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (218, 'Action Thrillers with Statham', '2026-03-03T10:59:33.735267'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (219, 'Dark Crime Thrillers - International Settings', '2026-03-03T05:14:43.144060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (220, 'Lighthearted romance/comedy preference', '2026-05-02T07:39:48.637464'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (221, 'Action-Comedy Franchises Dominate', '2026-03-03T11:13:47.673041'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (222, 'Preference for music‑focused and literary dramas', '2026-04-29T17:28:45.276314'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (223, 'Family Comedy Franchises', '2026-03-03T00:04:48.929586'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (224, 'High-Octane Action Franchises', '2026-03-03T10:34:53.777160'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (225, 'Action‑Crime/Adventure preference', '2026-05-02T07:37:43.236236'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (226, 'Historical Drama Focus', '2026-03-03T09:52:14.976754'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (227, 'Music Concert Documentaries', '2026-03-03T07:57:22.316959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (228, 'Comedy‑heavy genre mashups', '2026-04-29T09:42:48.600788'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (229, 'Preference for comedy‑infused titles', '2026-05-02T07:56:11.887326'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (230, 'Historical Music Dramas', '2026-03-03T10:42:41.675379'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (231, 'High-Concept Action Comedies', '2026-03-02T12:03:49.857353'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (232, 'Historical Period Dramas', '2026-03-03T11:14:34.518372'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (233, '{', '2026-03-03T10:56:50.193889'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (234, 'Action‑heavy crime thrillers vs drama/documentary', '2026-04-29T09:51:49.223018'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (235, 'Romantic Musicals & Concert Films', '2026-03-03T11:24:26.737597'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (236, 'Broad genre‑spanning pop‑culture and action preference', '2026-05-02T07:57:05.269508'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (237, '90s Family Comedies', '2026-03-02T12:20:17.498190'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (238, 'Historical/biographical drama preference', '2026-05-01T08:40:01.594269'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (239, 'Musical Biopics & Concert Films', '2026-03-03T07:47:04.692712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (240, '2025‑2026 recent theatrical movies', '2026-05-02T07:41:13.236924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (241, 'Preference for Character-Driven Dramas', '2026-03-03T00:09:41.734060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (242, 'Action‑Comedy/Adventure blend over serious drama', '2026-04-29T08:02:23.573052'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (243, 'Contemporary comedy‑drama & thriller series preference', '2026-05-02T07:46:51.396561'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (244, 'Prefers TV episodes over feature films', '2026-05-02T07:32:13.233700'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (245, 'Genre‑blending action/comedy and music documentary fans', '2026-05-02T07:39:14.724424'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (246, 'Historical Romance Focus', '2026-03-03T00:11:35.440473'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (247, 'Action and music documentary fans', '2026-04-30T07:45:04.000969'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (248, 'Music‑focused and romance‑driven dramatic titles', '2026-05-01T08:37:59.635117'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (249, 'Action‑driven high‑energy titles', '2026-04-29T07:50:37.639738'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (250, 'Lighthearted Fiction over Serious Documentary/Biopic', '2026-04-28T10:52:38.293869'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (251, 'Musical Romance Era Dramas', '2026-03-06T01:11:03.859680'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (252, '90s Action-Comedy Influence', '2026-03-03T00:15:28.815785'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (253, 'Action‑Crime Thriller Preference', '2026-05-01T08:40:09.423009'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (254, 'Action-Oriented Crime Dramas', '2026-03-03T09:59:04.770586'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (255, 'Preference for male‑centered protagonists', '2026-04-28T10:57:54.798767'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (256, 'High-Energy Action & Music Focus', '2026-03-03T08:30:37.569810'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (257, 'Grounded drama & real-life stories vs spectacle', '2026-04-27T01:22:55.225366'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (258, 'Character-Driven Historical Dramas', '2026-03-03T11:12:38.780534'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (259, 'Historical Crime Dramas', '2026-03-03T10:57:35.683503'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (260, 'Music‑centric films and documentaries', '2026-04-29T17:29:26.242075'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (261, 'Musical Concert Films & Animated Classics', '2026-03-03T00:21:12.306582'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (262, 'Historical Romance Dramas', '2026-03-03T08:12:31.749761'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (263, 'Preference for intimate character dramas', '2026-04-27T10:53:32.429061'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (264, 'Musical Concert Films Preferred', '2026-03-03T07:33:18.131580'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (265, 'Historical Sports Dramas', '2026-03-02T12:02:11.861136'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (266, 'Musical Romance Era Focus', '2026-03-03T11:09:35.426151'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (267, 'Feature-length narrative movies', '2026-04-29T07:58:30.787132'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (268, 'Dark Mystery Crime Dramas', '2026-03-03T10:11:43.191892'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (269, 'Historical Dramas with Ensemble Casts', '2026-03-03T10:31:56.744461'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (270, 'Niche drama & crime‑focused titles', '2026-04-29T17:15:29.849128'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (271, 'Musical Biopics & Concert Films', '2026-03-03T10:13:16.953108'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (272, 'Action-Comedy Genre Preference', '2026-03-03T10:23:06.162692'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (273, 'Crime‑action and genre‑blended blockbusters', '2026-05-02T07:37:20.484712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (274, 'Historical Romance Dramas', '2026-03-03T05:10:23.360093'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (275, 'Family-Friendly Animated Entertainment', '2026-03-03T10:58:23.074099'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (276, 'Historical Romance Dramas', '2026-03-03T08:39:05.332282'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (277, 'Musical Biopics & Concert Films', '2026-03-03T09:45:23.087071'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (278, 'Romantic Period Dramas', '2026-03-03T07:52:53.246490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (279, 'Romantic Musicals with Historical Settings', '2026-03-03T09:47:38.589041'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (280, 'Action‑driven spectacle lovers', '2026-04-29T09:53:14.055045'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (281, 'Historical Dramas with Strong Performances', '2026-03-03T09:57:33.158101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (282, 'Romantic Dramas with Historical Settings', '2026-03-03T08:00:06.454417'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (283, 'Character-Driven Dramas with Ensemble Casts', '2026-03-03T10:09:28.630785'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (284, 'Action Thrillers with Strong Leads', '2026-03-03T05:17:24.571517'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (285, 'Musical Concert Experiences', '2026-03-03T08:23:20.523411'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (286, 'Musicals and Concert Films', '2026-03-03T10:01:21.937922'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (287, 'Character-Driven Romantic Dramas', '2026-03-03T11:24:04.229161'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (288, 'Historical Romance Movie Focus', '2026-03-03T11:01:51.331990'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (289, 'Drama‑centric genre‑blending indie titles', '2026-04-30T07:36:38.675034'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (290, 'Prefers TV drama episodes over feature films', '2026-04-27T01:31:47.740719'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (291, 'Music & Live Performances Preference', '2026-03-03T09:45:00.765861'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (292, 'Musical Variety Entertainment Preferences', '2026-03-03T09:52:37.522576'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (293, 'Musical Biopics & Concert Films', '2026-03-03T00:18:55.475003'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (294, 'Historical Romance Dramas', '2026-03-03T10:34:31.311338'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (295, 'High-energy competition and live performance focus', '2026-04-29T09:48:20.183904'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (296, 'Historical Romance Dramas', '2026-03-03T08:43:11.751025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (297, 'Music‑centric biographical documentaries', '2026-04-29T17:16:01.195533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (298, 'Crime Dramas with Strong Leads', '2026-03-03T10:40:46.753370'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (299, 'Neil Diamond Tribute Acts', '2026-03-03T05:05:09.215615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (300, 'Action‑driven competition and performance titles', '2026-05-01T08:28:41.680674'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (301, 'High-Octane Action & Sci-Fi', '2026-03-03T04:52:31.312390'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (302, 'High-Concept Action Dramas', '2026-03-03T09:44:17.081091'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (303, 'High‑concept genre mashup films', '2026-05-01T08:32:35.934035'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (304, 'Edgy genre‑blends with crime, comedy, or action', '2026-04-29T17:19:00.837720'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (305, 'Historical Romance with Musical Elements', '2026-03-02T11:59:30.480618'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (306, 'Musical Concert Movie Preference', '2026-03-03T11:20:18.077711'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (307, 'Preference for feature-length movies over TV episodes', '2026-04-28T11:04:24.439101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (308, 'Musical Concert Movie Preference', '2026-03-03T07:36:37.580605'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (309, 'Musical Concert Films Dominate', '2026-03-03T10:07:35.789326'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (310, 'Family-Friendly Animated Comedy', '2026-03-03T08:10:58.665371'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (311, 'Historical Sports Dramas', '2026-03-03T05:02:51.731401'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (312, 'Action-Driven Crime Dramas', '2026-03-03T07:25:40.531102'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (313, 'Drama‑centric, character‑driven titles', '2026-05-02T07:56:48.521326'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (314, 'Historical Music Romance Dramas', '2026-03-03T04:56:23.920028'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (315, 'Niche drama series over mainstream blockbusters', '2026-04-29T09:51:41.687266'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (316, 'Preference for feature-length movies over episodes', '2026-04-27T11:08:24.144972'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (317, 'Adaptations of existing works', '2026-04-30T07:47:30.940067'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (318, 'Musical Concert Films', '2026-03-03T08:05:08.371680'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (319, '{', '2026-03-03T10:45:27.862767'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (320, 'High-Budget Dramatic Cinema', '2026-03-05T04:48:42.266563'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (321, 'Historical Music Dramas', '2026-03-03T10:19:37.369223'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (322, 'Grounded contemporary drama & documentary preference', '2026-04-27T01:18:50.738902'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (323, 'Action-Oriented Family Entertainment', '2026-03-03T08:19:06.656930'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (324, 'Historical Period Dramas - 20th Century', '2026-03-03T10:36:51.234363'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (325, 'Historical Romance with Action', '2026-03-03T00:23:30.001820'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (326, 'Dark Comedies with Crime Elements', '2026-03-03T09:43:54.665281'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (327, 'Historical Sports Dramas', '2026-03-02T12:18:44.129793'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (328, 'Musical Performance & Concert Films', '2026-03-03T07:23:21.965751'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (329, 'Musicals & Historical Dramas', '2026-03-03T08:02:02.938112'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (330, 'Romantic Musicals & Historical Dramas', '2026-03-03T10:21:35.615698'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (331, 'Historical Sport Dramas', '2026-03-03T08:22:57.889783'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (332, 'Romantic Dramas with Historical Settings', '2026-03-03T10:43:06.533451'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (333, 'Musicals & Historical Music Dramas', '2026-03-03T00:23:07.377538'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (334, 'Historical Sports Dramas', '2026-03-03T10:12:30.140694'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (335, 'Movie-format preference over TV episodes', '2026-04-28T11:07:26.578894'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (336, '{', '2026-03-03T08:07:32.153603'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (337, 'Action-Comedy Franchises with Strong Female Leads', '2026-03-03T10:45:51.354725'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (338, 'Musical Concert Films & Dramas', '2026-03-03T08:38:18.668531'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (339, 'Romantic Musicals & Concert Films', '2026-03-03T08:07:05.985765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (340, 'Historical Sports Dramas', '2026-03-02T12:00:18.084766'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (341, 'Action-Comedy Franchises Dominate', '2026-03-03T11:35:55.319103'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (342, 'Historical Romance Dramas', '2026-03-02T11:48:22.098787'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (343, 'Musical Concert Films', '2026-03-03T00:25:46.262172'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (344, 'Musical Family Dramas', '2026-03-03T11:11:52.497131'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (345, 'Prefers short-form, contemporary, genre‑blended content', '2026-05-02T07:36:44.841256'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (346, 'Historical Period Dramas', '2026-03-03T08:01:17.448682'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (347, 'Sport-Focused Dramas & Competitions', '2026-03-03T07:25:16.370574'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (348, 'Musical Family Biopics', '2026-03-03T04:47:22.876750'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (349, 'Sport-Focused Historical Dramas', '2026-03-03T10:22:43.594823'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (350, 'Romantic Musicals & Concert Films', '2026-03-03T11:13:24.661268'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (351, 'Musical Romance Dramas', '2026-03-04T04:46:30.409969'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (352, 'Preference for drama‑centric over action‑heavy titles', '2026-05-01T08:26:21.851482'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (353, 'Drama‑centric narratives vs music/action documentaries', '2026-04-29T09:56:42.043308'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (354, 'Action-Adventure Franchises', '2026-03-03T09:53:48.556062'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (355, 'Romantic Comedies with Family Focus', '2026-03-02T12:17:59.530224'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (356, 'Modern American-set mainstream titles', '2026-05-02T07:49:44.293797'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (357, 'Action Franchises with Strong Leads', '2026-03-03T07:58:55.909340'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (358, 'Romantic Musicals & Dramas', '2026-03-03T11:34:00.667020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (359, 'Historical Sports Dramas', '2026-03-02T12:06:09.460305'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (360, 'Historical Romance Dramas', '2026-03-03T04:46:13.355904'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (361, 'Musicals and Concert Films', '2026-03-03T00:13:09.470080'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (362, 'Romantic Musicals & Concert Films', '2026-03-03T00:14:42.291954'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (363, 'Action-Comedy Genre Blend', '2026-03-03T00:05:12.377506'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (364, 'Musical Concert Experiences', '2026-03-03T11:06:31.410737'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (365, 'Preference for high‑stakes competition and action', '2026-04-29T08:06:55.821113'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (366, 'Musical Romance Era - 2020s', '2026-03-03T04:49:29.400481'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (367, 'Musical Concert Experiences', '2026-03-03T08:26:55.331250'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (368, 'TV episodes over feature‑length movies', '2026-04-27T01:23:48.452437'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (369, 'Musical Romance Era Focus', '2026-03-03T11:30:54.983821'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (370, 'Musical Performance Preference', '2026-03-03T07:30:36.069554'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (371, 'Action-Comedy Franchises Dominate', '2026-03-03T08:33:17.365677'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (372, 'Short-form TV episodes vs long feature films', '2026-04-27T01:32:31.408318'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (373, 'Historical Romance Movie Focus', '2026-03-03T10:44:39.758910'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (374, 'Preference for real-life cultural/industry biographical stories', '2026-04-29T17:32:24.095616'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (375, 'Historical Drama with Strong Leads', '2026-03-03T08:14:27.935638'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (376, 'Action Comedies with Strong Leads', '2026-03-03T11:29:45.978023'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (377, 'Historical Period Pieces', '2026-03-03T09:54:35.143095'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (378, 'Preference for feature-length movies over TV episodes', '2026-04-29T17:14:08.375146'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (379, 'Action Comedies with Strong Leads', '2026-03-03T00:14:19.390717'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (380, 'Action Comedies with Strong Leads', '2026-03-03T08:09:06.401046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (381, '{', '2026-03-03T07:35:06.951000'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (382, 'Real‑world profession & pop‑culture stories', '2026-04-29T09:55:03.761798'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (383, 'Drama TV episodes over movies', '2026-04-27T10:51:02.543188'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (384, 'Western Crime Drama Focus', '2026-03-03T08:32:09.184260'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (385, 'Musicals & Historical Dramas', '2026-03-03T10:10:35.792852'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (386, 'Historical Music Biopics', '2026-03-03T11:09:11.622393'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (387, 'Drama & biography preference vs action thrillers', '2026-04-30T07:38:49.865020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (388, 'Modern workplace‑centric dramedies', '2026-05-01T08:27:41.965581'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (389, 'Preference for intimate drama over high‑concept action', '2026-04-27T01:33:24.262118'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (390, 'Franchise-Driven Action Dramas', '2026-03-03T07:50:30.133663'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (391, 'Crime Thrillers with Strong Leads', '2026-03-03T10:48:34.406203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (392, 'Big‑budget, star‑driven movies vs TV episodes', '2026-05-02T07:47:48.095623'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (393, 'Romantic Dramas with Historical Settings', '2026-03-03T07:47:27.054368'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (394, 'Historical Dramas with Strong Male Leads', '2026-03-03T11:14:58.502655'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (395, 'Historical Romance Dramas', '2026-03-03T11:26:20.063667'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (396, 'Prefers period, fantasy, or futuristic settings', '2026-04-27T11:07:33.231570'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (397, 'Artistic‑focused drama over genre‑heavy plots', '2026-04-29T08:07:18.979029'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (398, 'Action-Comedy Franchises with Strong Leads', '2026-03-02T12:09:13.898107'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (399, 'Dark Comedies & Crime Dramas', '2026-03-03T11:32:28.770132'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (400, 'Historical Crime Dramas with Strong Leads', '2026-03-03T11:00:20.890596'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (401, 'Big-Budget Music Concerts & Action Dramas', '2026-03-03T10:46:37.612108'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (402, 'Musical Romance Era Focus', '2026-03-03T07:38:33.058753'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (403, 'Romantic Period Dramas', '2026-03-03T11:21:02.174233'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (404, 'Romantic Dramas with Musical Elements', '2026-03-03T07:31:45.906691'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (405, 'Music‑focused performer narratives', '2026-04-29T17:23:17.636762'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (406, 'Historical Drama with Ensemble Casts', '2026-03-02T23:30:11.086181'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (407, 'Romantic Comedy Focus', '2026-03-04T04:42:13.260746'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (408, 'Career breakthrough and achievement narratives', '2026-04-28T10:48:24.981764'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (409, 'Dark Comedy Crime Series', '2026-03-03T08:16:23.792205'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (410, 'Action-Comedy Franchises with Ensemble Casts', '2026-03-03T10:18:05.979488'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (411, 'Spectacle‑heavy action & music concert films', '2026-05-01T07:50:52.949241'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (412, 'Preference for upbeat, spectacle‑driven entertainment', '2026-04-29T08:05:51.004970'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (413, 'Action‑Comedy Crime Spectacle Preference', '2026-04-29T17:14:27.875673'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (414, 'Musical Concert Films', '2026-03-03T10:17:41.116835'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (415, 'Prefers franchise or brand‑based feature films', '2026-04-28T11:03:29.410568'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (416, 'Real‑world biopic & documentary titles', '2026-04-28T11:04:43.873106'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (417, 'Music-Driven Historical Romance', '2026-03-03T10:07:12.911830'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (418, 'Action-Oriented Crime Dramas', '2026-03-03T08:12:08.941615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (419, 'Action Comedies with Ensemble Casts', '2026-03-03T10:32:20.447795'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (420, 'Romantic Musicals & Concert Films', '2026-03-03T11:02:13.731715'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (421, 'Historical Music Dramas', '2026-03-03T10:54:53.297963'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (422, 'Drama-centric titles vs crime/action thrillers', '2026-04-29T17:17:19.784687'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (423, 'Dark Comedies with Strong Male Leads', '2026-03-03T00:20:49.825831'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (424, 'Historical Romance Dramas', '2026-03-03T05:04:46.534164'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (425, 'Historical Period Pieces Romance', '2026-03-03T11:15:22.232967'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (426, 'Musical Biopic Preferences', '2026-03-04T04:51:39.411387'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (427, 'Romantic Musicals & Family Comedies', '2026-03-03T09:59:51.389477'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (428, 'Musical Romance Dramas', '2026-03-03T11:35:31.817524'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (429, 'Romantic Comedies with Family Dynamics', '2026-03-03T08:21:48.370147'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (430, 'Historical Romance Movie Focus', '2026-03-03T10:41:09.680828'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (431, 'Historical Romance Dramas', '2026-03-03T09:54:12.395656'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (432, 'Action-Comedy Franchises with Ensemble Casts', '2026-03-03T08:04:22.957669'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (433, 'Darker Genre Blend: Crime & Thriller', '2026-03-03T07:57:45.851820'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (434, 'Action Comedies with Strong Leads', '2026-03-03T11:22:31.911077'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (435, 'Music documentaries and concert films', '2026-04-30T07:46:10.374510'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (436, 'Music and Romance‑focused Films over Action/Sport', '2026-04-30T07:38:42.065937'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (437, 'Prefers TV episodes over feature films', '2026-04-28T10:55:17.958353'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (438, 'Musical Concert Films', '2026-03-03T11:20:39.927530'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (439, 'Musical Concert & Family Favorites', '2026-03-03T05:18:09.087110'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (440, 'Romantic Musicals with Historical Settings', '2026-03-03T11:27:50.915056'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (441, 'Musical Concert & Family Entertainment', '2026-03-03T07:48:11.131949'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (442, 'High‑energy genre‑mix movies vs drama/TV episodes', '2026-04-30T07:39:38.315689'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (443, 'High-Octane Action Comedies', '2026-03-03T05:12:00.777307'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (444, 'Musical Biopics & Concert Films', '2026-03-03T11:00:43.970645'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (445, 'Action-Comedy Franchises', '2026-03-03T07:33:41.110734'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (446, 'Musical Concert Films', '2026-03-03T10:14:49.783037'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (447, 'High-Octane Action Comedies', '2026-03-02T12:10:45.279856'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (448, 'Western Crime Dramas', '2026-03-03T08:02:25.109112'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (449, 'High-Octane Action Dramas', '2026-03-03T08:30:15.256135'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (450, 'Historical Music Biopics', '2026-03-03T04:52:53.357170'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (451, 'Crime Dramas with Strong Leads', '2026-03-02T11:58:20.245086'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (452, 'Historical Romance Dramas', '2026-03-03T09:49:31.882917'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (453, 'Romantic Period Dramas', '2026-03-03T10:09:05.944630'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (454, 'High-Octane Action Comedies', '2026-03-02T11:54:51.682630'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (455, 'Action-Adventure Family Focus', '2026-03-03T08:35:40.638628'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (456, 'Recent grounded dramas and live‑performance documentaries', '2026-05-01T07:50:31.621260'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (457, 'Music‑centric and light‑hearted pop culture titles', '2026-04-30T07:48:07.294568'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (458, 'Romantic Comedies with Ensemble Casts', '2026-03-03T11:07:18.437405'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (459, 'Musical Concert Experiences', '2026-03-03T10:37:37.927412'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (460, 'Action-Comedy Franchise Focus', '2026-03-03T11:31:19.052545'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (461, 'Action-Comedy Genre Blend', '2026-03-03T11:05:46.880184'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (462, 'Romantic Musicals & Dramas', '2026-03-03T07:28:40.483593'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (463, 'Action-Comedy Crime Franchises', '2026-03-03T09:56:22.939336'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (464, 'Romantic Musicals & Concert Films', '2026-03-03T10:48:57.331985'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (465, 'Romantic Period Dramas', '2026-03-03T08:32:30.942593'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (466, 'Romance‑driven / light‑hearted titles vs gritty crime/action', '2026-04-29T09:59:46.371533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (467, 'Dark Comedy Action', '2026-03-02T12:05:21.012955'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (468, 'Drama‑focused titles (often romance or crime)', '2026-04-29T17:24:30.094430'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (469, '90s Romantic Comedies', '2026-03-03T07:30:12.569006'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (470, 'Action‑drama with strong director signatures', '2026-05-02T07:43:46.423932'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (471, 'Musical Concert Documentaries', '2026-03-03T10:25:24.079875'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (472, 'Prefers theatrical movies over TV episodes', '2026-05-01T08:23:11.820747'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (473, 'Character-Driven Dramas & Intense Relationships', '2026-03-03T10:53:19.785385'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (474, 'Romantic Period Dramas', '2026-03-03T11:30:33.373980'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (475, 'Contemporary slice‑of‑life episodes & music docs', '2026-04-30T07:48:35.157138'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (476, 'Action-Focused Sports Dramas', '2026-03-03T10:45:02.957390'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (477, 'Preference for light‑hearted pop‑culture and music entertainment', '2026-05-02T07:50:23.392272'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (478, 'Historical Romance Movie Focus', '2026-03-03T00:30:47.738336'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (479, 'Musical Variety & Ensemble Comedy', '2026-03-03T07:24:07.687409'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (480, 'Action Comedies with High-Profile Casts', '2026-03-03T11:05:23.022102'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (481, 'Western Crime Dramas', '2026-03-03T11:02:36.564547'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (482, 'Musical Concert Film Preference', '2026-03-03T05:15:28.425543'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (483, 'Action-Comedy Franchises', '2026-03-03T07:27:55.467520'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (484, 'Prefers TV episodes rather than feature films', '2026-05-01T08:29:25.676024'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (485, 'Action Comedies with Ensemble Casts', '2026-03-03T09:49:09.134722'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (486, 'Contemporary crime‑thriller and comedy blends', '2026-04-29T09:46:44.690452'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (487, 'Franchise-Driven Action Dramas', '2026-03-03T10:58:00.346898'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (488, 'Historical Sports Dramas', '2026-03-03T11:23:42.234471'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (489, 'Historical Dramas with Strong Female Leads', '2026-03-03T07:54:23.345836'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (490, 'Preference for artistic‑creative stories over institutional dramas', '2026-04-28T11:00:43.884490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (491, 'Music Concert & Sports Dramas', '2026-03-03T10:28:50.661887'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (492, 'TV drama/comedy episodes over action movies', '2026-05-01T08:36:50.496212'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (493, 'Romantic Comedies with Strong Female Leads', '2026-03-03T00:10:26.948406'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (494, 'Action Comedies with Ensemble Casts', '2026-03-03T00:13:55.764354'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (495, 'Romantic Comedies with Established Franchises', '2026-03-02T12:09:59.770880'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (496, 'Fans of adaptations of famous IP/biographies', '2026-04-30T07:51:06.443100'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (497, 'Musical Concert Films Predominate', '2026-03-03T05:17:47.544724'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (498, 'Romantic Musicals & Dramas', '2026-03-04T05:03:42.776827'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (499, 'Gritty action‑crime thriller preference', '2026-04-28T10:48:45.089402'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (500, 'High-Budget Action & Sci-Fi Dramas', '2026-03-03T10:12:53.899070'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (501, 'Romantic Musicals & Historical Dramas', '2026-03-04T04:50:27.889417'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (502, 'Preference for feature films over TV episodes', '2026-05-02T07:31:27.917410'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (503, 'Neil Diamond Tribute Musicals', '2026-03-03T10:08:44.249496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (504, 'Prefers TV episodes over feature films', '2026-05-02T07:53:59.363289'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (505, 'Dark Crime Dramas', '2026-03-03T09:48:01.160960'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (506, 'Gritty crime‑thriller and action dramas', '2026-04-29T07:57:19.415146'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (507, 'Comedy‑driven, action‑oriented titles', '2026-05-01T08:24:12.250878'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (508, 'Musical Concert Films', '2026-03-03T10:23:28.765025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (509, 'Prefers fiction movies over music/documentary content', '2026-04-29T17:31:38.630068'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (510, '{', '2026-03-03T10:40:23.842468'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (511, 'Action/Adventure Franchises', '2026-03-03T10:47:01.681035'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (512, 'High-Budget Action Comedies', '2026-03-03T05:16:13.568106'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (513, 'Slice-of-life character dramas vs action thrillers', '2026-05-02T07:47:17.855685'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (514, 'Prefers feature-length movies over short TV episodes', '2026-04-29T08:07:06.392114'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (515, 'Music documentaries and concert films', '2026-05-01T08:24:49.216254'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (516, 'Historical Drama Romance', '2026-03-03T08:17:32.901613'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (517, 'Serious drama preference (no comedy)', '2026-04-27T01:24:08.764693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (518, 'Historical Romance Dramas', '2026-03-03T05:11:13.556519'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (519, 'Prefers feature films over TV episodes', '2026-05-01T08:23:26.653972'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (520, 'Romantic Period Dramas - Historical Settings', '2026-03-03T09:46:54.004866'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (521, 'Preference for grounded drama over action spectacle', '2026-04-28T11:07:17.020727'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (522, 'High-Octane Action Dramas', '2026-03-05T04:45:39.858679'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (523, 'Music‑centric and family‑friendly titles', '2026-03-07T08:28:37.328545'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (524, '{', '2026-03-03T08:06:21.689804'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (525, 'Musical Variety Show Preferences', '2026-03-03T10:26:56.389180'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (526, 'Musical Romance Era Focus', '2026-03-03T07:38:09.029386'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (527, 'Musical Concert Films & Franchises', '2026-03-02T11:52:34.756234'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (528, 'Performance-focused entertainment industry narratives', '2026-04-30T07:37:32.605162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (529, 'Action‑Comedy/Adventure vs Romance‑Drama', '2026-05-02T07:48:16.113356'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (530, 'Action-Comedy Genre Blend', '2026-03-03T08:11:45.426340'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (531, 'Neil Diamond Musical Biopics', '2026-03-03T08:40:14.609088'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (532, 'Male‑lead dramas vs female‑lead titles', '2026-04-29T09:50:51.076849'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (533, 'Franchise-Driven Family Entertainment', '2026-03-03T08:36:03.023959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (534, 'TV episodes over feature films', '2026-04-29T09:52:46.903277'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (535, 'Action‑Adventure/Crime genre blend', '2026-05-02T07:42:44.346882'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (536, 'Historical Sports Dramas', '2026-03-03T11:10:43.132141'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (537, 'Action-Comedy Franchise Focus', '2026-03-03T10:59:57.177899'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (538, 'Romantic Musicals with Historical Settings', '2026-03-04T04:49:38.362325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (539, 'Historical Romance Action Dramas', '2026-03-03T00:07:45.045692'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (540, 'High‑concept action and genre‑mix titles', '2026-05-02T07:45:58.191063'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (541, 'Historical Crime Dramas', '2026-03-03T09:43:09.087897'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (542, 'Historical Romance with Dramatic Tension', '2026-03-03T11:21:45.892891'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (543, 'TV episodes over feature-length movies', '2026-04-28T10:59:36.445714'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (544, 'High-Octane Sports Dramas', '2026-03-03T07:58:32.766386'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (545, 'Underdog-focused dramatic narratives', '2026-04-30T07:40:36.898025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (546, 'Romantic Dramas with Strong Female Leads', '2026-03-03T11:08:49.825101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (547, '{', '2026-03-03T08:12:57.859747'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (548, 'Historical Dramas with Strong Leads', '2026-03-02T12:06:54.859348'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (549, 'Musical Concert Experiences', '2026-03-03T10:53:42.717029'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (550, 'Real-life biographies and documentaries', '2026-05-01T08:30:35.978835'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (551, 'Preference for romance-driven titles', '2026-04-30T07:49:43.480237'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (552, 'Arts‑focused dramatic narratives', '2026-04-27T01:13:34.101396'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (553, 'High-Octane Action Dramas', '2026-03-03T11:34:46.425979'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (554, 'Franchise-Driven Family Entertainment', '2026-03-03T10:39:35.340478'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (555, 'Action-Comedy Franchise Preference', '2026-03-03T08:14:05.253300'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (556, 'High‑energy genre spectacles vs grounded dramas', '2026-05-01T08:39:38.192489'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (557, 'Romantic Dramas with Family Themes', '2026-03-03T08:10:14.404289'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (558, 'Romantic Dramas with Historical Elements', '2026-03-03T10:34:08.013855'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (559, 'Musical Concert Experiences', '2026-03-03T00:08:56.807864'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (560, 'Action-Comedy Crime Dramas', '2026-03-03T04:54:29.955515'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (561, 'Historical Period Pieces', '2026-03-02T12:00:40.445251'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (562, 'Romantic Historical Dramas', '2026-03-03T10:36:25.503209'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (563, 'Action/Crime/Sport over Romance/Documentary', '2026-04-29T09:55:32.056621'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (564, 'Historical Music Romance Dramas', '2026-03-03T10:49:19.610080'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (565, 'Action-Comedy Franchise Focus', '2026-03-03T10:56:24.577291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (566, '90s Comedy Romances', '2026-03-03T07:23:46.109739'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (567, 'Prefers movies over TV episodes', '2026-04-29T17:29:08.972394'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (568, 'Preference for high‑stakes competition or spectacle', '2026-05-01T08:40:23.962883'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (569, 'Historical Period Pieces', '2026-03-03T00:15:51.478726'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (570, 'Prefers movies over TV episodes', '2026-04-27T01:33:08.629907'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (571, 'Romantic Comedies with Ensemble Casts', '2026-03-03T08:15:37.819921'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (572, 'Historical Dramas with Strong Male Leads', '2026-03-03T11:16:47.193669'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (573, 'Action‑Comedy Adventure over Romance/Music Documentary', '2026-04-27T01:37:15.562905'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (574, 'High-Stakes Competition and Performance Settings', '2026-05-02T07:43:31.292732'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (575, 'Romance‑focused drama preference', '2026-04-29T09:45:40.311978'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (576, 'Dark Comedy Crime Dramas', '2026-03-03T08:19:29.346684'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (577, 'Musical Concert Films', '2026-03-04T04:59:26.161627'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (578, 'Gritty crime/action and high‑stakes drama', '2026-04-29T09:53:52.239967'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (579, 'Historical Dramas with Strong Performances', '2026-03-03T00:20:26.498226'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (580, 'Musicals and Concert Films', '2026-03-03T05:08:05.884323'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (581, 'Romantic Dramas with Strong Relationships', '2026-03-03T08:08:19.130379'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (582, 'Romantic Musicals & Period Dramas', '2026-03-03T08:36:25.672434'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (583, 'Action-Crime Thrillers with Strong Leads', '2026-03-03T00:25:01.746121'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (584, 'Short, genre‑mix comedy/action episodes', '2026-04-29T08:10:32.370061'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (585, 'Family-Friendly Animated Comedies', '2026-03-04T04:59:48.024535'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (586, 'Romantic Musicals & Concert Films', '2026-03-03T07:42:50.721780'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (587, 'Action-Comedy Crime Franchises', '2026-03-03T08:03:33.975551'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (588, 'Action-Focused Crime Dramas', '2026-03-02T23:27:27.464582'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (589, 'Competitive high‑pressure professional settings', '2026-04-27T01:36:21.984025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (590, 'Historical Music Franchises', '2026-03-03T08:35:16.892669'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (591, 'Historical Romance Dramas', '2026-03-03T05:17:00.498152'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (592, 'Action Comedy Franchises', '2026-03-03T00:17:45.016462'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (593, 'Action-Comedy Franchises', '2026-03-03T11:11:07.215637'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (594, 'Romantic Musicals & Concert Films', '2026-03-03T08:38:42.036157'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (595, 'Musical Romance Dramas', '2026-03-03T11:33:38.343340'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (596, 'Animated Family Blockbusters', '2026-03-03T07:51:18.734687'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (597, 'Music‑centric and genre‑blending titles', '2026-05-02T07:34:35.709022'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (598, 'Romantic Period Dramas', '2026-03-03T00:28:51.793381'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (599, 'Action-Comedy Franchise Preferences', '2026-03-03T05:06:27.585454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (600, 'Romantic Musicals with Historical Settings', '2026-03-03T11:03:25.835278'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (601, 'Romantic Musicals & Family Animation', '2026-03-03T08:03:11.078669'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (602, 'Historical Music Dramas', '2026-03-03T00:22:44.507322'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (603, 'Crime‑centric genre blends vs biographical dramas', '2026-05-01T08:39:48.394637'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (604, 'Crime Dramas with Family Themes', '2026-03-03T10:43:29.476495'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (605, 'Crime‑comedy and action‑driven mainstream titles', '2026-04-29T17:30:47.125753'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (606, 'Action Comedies with Strong Leads', '2026-03-03T00:26:56.520928'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (607, 'Animated Family Entertainment', '2026-03-03T11:36:18.849804'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (608, 'Musical Biopics & Concert Films', '2026-03-04T04:45:41.345729'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (609, 'Dark Comedy Dramas', '2026-03-03T10:12:07.321548'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (610, 'Historical Music Romance Dramas', '2026-03-03T04:59:41.286117'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (611, 'Modern gritty genre blends vs period romance/music', '2026-05-02T07:46:39.702994'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (612, 'Romantic Comedies with Family', '2026-03-03T10:33:45.527098'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (613, 'Musical Tribute Performances', '2026-03-03T11:28:59.254928'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (614, 'Crime Thrillers with Strong Leads', '2026-03-02T23:27:49.067617'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (615, 'Music-Driven Action Dramas', '2026-03-04T04:58:36.242890'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (616, 'Historical Dramas with Strong Male Leads', '2026-03-03T08:03:57.364561'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (617, 'Workplace/industry‑focused character dramas', '2026-04-30T07:46:34.263978'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (618, 'Character-Driven Family Comedies', '2026-03-03T07:26:25.249722'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (619, 'Romantic Dramas with Historical Settings', '2026-03-03T08:42:01.871340'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (620, 'Historical Sports Dramas', '2026-03-04T04:50:51.334368'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (621, 'Period romance and historical drama', '2026-04-29T17:16:21.935974'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (622, 'Music‑centric films and episodes', '2026-04-29T07:51:06.067903'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (623, 'Romantic Period Dramas', '2026-03-02T12:09:36.618155'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (624, '90s Rom-Coms & Action Dramas', '2026-03-03T07:22:12.282587'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (625, 'Historical Music Romance Dramas', '2026-03-03T08:31:46.913736'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (626, 'Action-Comedy Genre Preference', '2026-03-03T07:26:02.932253'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (627, 'Action-Oriented Blockbuster Preferences', '2026-03-03T09:59:28.581422'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (628, 'TV episodes & music documentaries vs mainstream films', '2026-04-30T07:50:01.438467'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (629, 'Indie artist‑focused dramas vs mainstream blockbusters', '2026-04-29T09:53:26.086274'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (630, 'Action-Driven Sports Dramas', '2026-03-03T10:20:01.660407'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (631, 'Character-Driven Dramas with Strong Leads', '2026-03-03T08:29:29.008169'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (632, 'Modern genre‑mix narrative movies over documentaries/period pieces', '2026-05-02T07:55:06.856224'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (633, 'Historical Music Dramas', '2026-03-03T10:22:20.034756'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (634, 'Action‑Crime thrillers vs. drama/biography', '2026-05-02T07:56:21.449709'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (635, 'Preference for drama‑centric narrative fiction', '2026-04-28T10:54:13.271735'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (636, 'Music-focused documentaries and biopics', '2026-05-01T08:39:00.660095'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (637, 'Dark Comedies with Strong Female Leads', '2026-03-03T08:29:51.858364'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (638, 'Action-Comedy Crime Franchises', '2026-03-03T08:34:03.463098'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (639, 'Historical Romance Musicals', '2026-03-03T10:30:22.528541'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (640, 'Action-Comedy Franchises', '2026-03-03T10:02:54.169325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (641, 'Musical Concert Films', '2026-03-03T11:06:09.448342'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (642, 'Musicals & Action Franchises', '2026-03-03T08:36:47.925806'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (643, 'Action Crime Thrillers', '2026-03-03T10:29:59.449414'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (644, 'Action Comedies with Strong Leads', '2026-03-04T05:02:02.802706'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (645, 'Contemporary real‑world drama preference', '2026-04-27T10:59:59.462835'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (646, 'Historical Crime Dramas', '2026-03-03T08:13:42.420510'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (647, 'Musical Concert Experiences', '2026-03-03T08:00:28.931444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (648, 'Historical Drama with Ensemble Casts', '2026-03-03T10:06:01.937347'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (649, 'Historical romance and music‑centric dramas', '2026-04-30T07:45:14.655816'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (650, 'Action-Oriented Crime Dramas', '2026-03-03T00:28:27.102368'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (651, 'Action-Comedy Franchises', '2026-03-03T07:59:19.327776'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (652, 'Short, genre‑blended TV episodes over long feature films', '2026-04-30T07:49:28.181556'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (653, 'Crime Thrillers with Strong Female Leads', '2026-03-03T09:45:44.912610'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (654, 'Historical Sports Dramas', '2026-03-03T10:03:17.560613'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (655, '{', '2026-03-02T12:16:46.310532'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (656, 'Historical Western Action Dramas', '2026-03-03T11:32:52.552454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (657, 'Historical Drama Focus', '2026-03-03T05:18:32.227217'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (658, 'Action-Comedy Crime Franchises', '2026-03-03T10:47:24.597996'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (659, 'Musical Concert Films & Dramas', '2026-03-03T07:53:59.849482'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (660, 'Niche, genre‑blending drama over mainstream blockbusters', '2026-04-27T01:33:37.065348'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (661, 'Preference for niche‑interest, genre‑blending titles', '2026-04-30T07:44:14.210322'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (662, 'Prefers TV episodes over feature films', '2026-04-27T01:36:40.740133'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (663, 'Prefers TV episodes over feature films', '2026-04-29T07:53:50.513152'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (664, 'Musical Concert Film Preference', '2026-03-03T11:24:49.362291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (665, 'Action‑Comedy/Crime preference', '2026-04-29T09:59:32.721684'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (666, 'Historical Music Biopics', '2026-03-03T07:44:00.573391'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (667, 'Music/Showbiz Creation & Industry Stories', '2026-05-02T07:34:07.340784'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (668, 'Romantic Dramas with Ensemble Casts', '2026-03-03T10:38:48.484203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (669, 'Dark Mystery Dramas', '2026-03-03T11:07:40.612717'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (670, 'Romance‑driven storytelling preference', '2026-05-01T08:25:59.222926'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (671, 'Recent 2026 scripted episodic releases', '2026-04-27T11:05:17.522068'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (672, 'Preference for crime‑drama and competitive biopic blends', '2026-04-30T07:39:13.468855'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (673, 'Historical Romance with Musical Elements', '2026-03-03T11:09:57.867053'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (674, 'Musicals & Concert Films', '2026-03-03T10:19:14.111886'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (675, 'Performance‑focused biopics and spectacle films', '2026-04-29T17:27:35.636045'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (676, 'Romantic Musicals & Concert Films', '2026-03-03T07:54:45.213399'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (677, 'Prefers music/romance films over action/crime thrillers', '2026-04-29T17:25:18.318992'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (678, 'Historical Music Biographies', '2026-03-03T09:48:23.020402'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (679, 'Historical Sports Dramas', '2026-03-03T11:19:32.040467'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (680, 'Drama‑centric, darker‑tone titles', '2026-05-01T08:31:36.216623'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (681, 'Animated Family Blockbusters', '2026-03-03T07:36:15.025560'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (682, 'Musical Concert Films', '2026-03-03T07:22:58.481422'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (683, '{', '2026-03-03T10:17:18.205633'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (684, 'Prestige dramas and character‑driven narratives', '2026-04-29T09:46:04.458938'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (685, 'Genre‑blending, comedy‑action preference', '2026-04-30T07:43:20.529615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (686, 'Crime Dramas with Strong Leads', '2026-03-03T10:42:18.356932'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (687, 'Music Concert Dramas', '2026-03-03T00:16:36.894362'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (688, 'Historical Music Biopics', '2026-03-05T04:57:59.211133'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (689, 'Romantic Musicals and Concert Films', '2026-03-03T11:10:19.878638'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (690, 'TV episodes over feature-length movies', '2026-05-02T07:38:50.371933'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (691, 'Musical Concert Films', '2026-03-03T10:00:14.369549'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (692, 'Work/Crime focus vs Romance/Music focus', '2026-05-02T07:45:40.128820'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (693, 'Fast‑paced comedy‑action blends', '2026-05-02T07:32:48.535819'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (694, 'Prefers TV episodes over feature-length movies', '2026-05-01T08:32:52.958140'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (695, 'Historical Romance Dramas', '2026-03-03T07:49:44.816195'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (696, 'Historical Dramas with Strong Male Leads', '2026-03-03T10:54:05.593872'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (697, 'Romantic Comedies with Strong Female Leads', '2026-03-03T10:35:39.541046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (698, 'Serious, conflict‑driven drama preference', '2026-05-01T08:31:57.863615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (699, 'Historical Romance Dramas', '2026-03-03T08:10:36.620418'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (700, 'Action-Comedy Franchises', '2026-03-03T07:46:19.036812'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (701, 'Musical Concert Documentaries', '2026-03-03T08:06:43.593062'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (702, 'Arts‑centric performance and music‑focused narratives', '2026-05-01T08:30:47.577195'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (703, 'Action-Driven Historical Dramas', '2026-03-03T04:52:06.330276'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (704, 'Prefers scripted narrative drama over documentaries', '2026-04-27T10:50:22.087490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (705, 'Diverse genre‑blend preference', '2026-04-29T07:59:36.320172'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (706, 'Historical Music Biographies', '2026-03-03T10:29:37.294892'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (707, 'Animated Family Comedies', '2026-03-03T07:41:15.437916'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (708, 'Historical Music Dramas', '2026-03-03T09:51:51.954237'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (709, 'Action Comedies with Strong Leads', '2026-03-03T11:06:54.902300'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (710, 'Historical Music Romance Dramas', '2026-03-03T10:36:02.424534'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (711, 'Preference for high‑octane action and competition', '2026-05-02T07:55:33.597429'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (712, 'Historical Sports Dramas', '2026-03-03T00:26:09.817806'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (713, 'Historical Music Romance Dramas', '2026-03-03T08:13:20.960396'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (714, 'Historical Period Pieces Dramas', '2026-03-03T11:32:06.389652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (715, 'Historical Romance Dramas', '2026-03-03T07:38:56.413319'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (716, 'Western Crime Dramas', '2026-03-03T10:52:56.609932'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (717, 'Music Concert Documentaries', '2026-03-03T08:37:56.022307'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (718, 'Musical Variety Entertainment', '2026-03-03T05:01:44.304415'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (719, 'Historical Western Crime Dramas', '2026-03-03T07:27:33.890758'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (720, 'Recent comedy‑drama & action‑adventure series', '2026-03-06T01:16:50.104414'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (721, 'Preference for high‑profile blockbuster movies', '2026-04-29T09:58:08.514854'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (722, 'Historical Sports Dramas', '2026-03-04T05:11:14.095203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (723, 'Character-driven dramedy & documentary over action spectacle', '2026-05-01T08:31:46.124041'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (724, 'Musical Biopics with Historical Context', '2026-03-03T10:49:42.254200'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (725, 'Romantic Dramas with Musical Elements', '2026-03-03T11:30:10.601116'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (726, 'Musical Variety Entertainment Preferences', '2026-03-03T11:25:11.662588'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (727, 'Musicals & Action Franchises', '2026-03-04T05:09:00.892997'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (728, 'Romantic Musicals with Historical Context', '2026-03-03T11:17:58.843669'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (729, 'Historical/arts‑focused dramas over modern action', '2026-04-28T11:06:04.259219'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (730, 'Musical Concert Experiences', '2026-03-03T09:47:16.294328'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (731, 'Modern realistic dramas & comedies vs period/fantasy settings', '2026-05-02T07:38:42.386490'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (732, '90s Rom-Com Nostalgia', '2026-03-03T08:39:28.946070'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (733, 'Action-Oriented Crime Thrillers', '2026-03-03T11:19:09.790275'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (734, 'Crime Thrillers with Strong Leads', '2026-03-03T09:53:00.820087'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (735, 'Dark Comedy Dramas', '2026-03-03T09:55:59.576353'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (736, 'Drama‑focused TV episodes vs feature films', '2026-05-02T07:36:28.704854'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (737, 'Romantic Musicals & Family Comedies', '2026-03-05T04:43:56.565774'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (738, 'Romantic Period Dramas', '2026-03-03T11:28:36.388731'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (739, 'High-Octane Action Comedies', '2026-03-03T10:30:45.958883'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (740, 'Action‑heavy, high‑intensity content', '2026-04-29T09:53:06.119227'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (741, '90s & 2000s Action Comedies', '2026-03-03T10:24:16.656485'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (742, 'Romantic Dramas with Historical Settings', '2026-03-03T08:25:45.156911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (743, '90s Animated Family Films', '2026-03-03T11:11:30.081421'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (744, 'Family-Focused Animated Comedy', '2026-03-03T07:52:03.541736'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (745, 'Historical Sport Dramas', '2026-03-03T07:43:13.494712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (746, 'Historical Romance Musicals', '2026-03-03T10:50:04.309862'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (747, 'Romantic Musicals with Historical Settings', '2026-03-03T10:57:12.720533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (748, 'Action‑Crime Comedy Feature Films', '2026-04-29T09:55:18.165363'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (749, 'Music documentaries and modern TV episodes', '2026-04-29T17:29:46.778063'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (750, 'Preference for biographical or real‑world subject content', '2026-05-01T08:33:14.304568'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (751, 'Prefers episodic, genre‑blending series over films', '2026-04-29T17:27:44.404536'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (752, 'Historical Dramas with Strong Leads', '2026-03-03T10:25:47.622664'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (753, 'Romantic Musicals & Family Films', '2026-03-03T08:16:01.696696'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (754, 'Niche indie dramas vs mainstream blockbusters', '2026-05-01T08:28:20.996716'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (755, 'Musical Concert Movie Preferences', '2026-03-03T11:21:23.852738'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (756, 'Musical Concert & Family Comedies', '2026-03-03T07:32:54.619281'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (757, 'Action-Focused Crime Dramas', '2026-03-02T11:59:52.463232'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (758, 'Crime Thrillers with Strong Leads', '2026-03-03T11:03:48.414587'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (759, 'Historical Sports Dramas', '2026-03-03T00:30:24.510578'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (760, 'Action-Driven Crime Dramas', '2026-03-03T11:27:05.080567'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (761, 'Drama paired with distinct secondary genre', '2026-05-02T07:43:06.859866'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (762, 'Musical Fan Engagement & Concert Films', '2026-03-03T05:08:29.703057'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (763, 'Action Thrillers with Strong Leads', '2026-03-03T11:08:25.626437'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (764, 'Musicals & Concert Films Preferred', '2026-03-03T11:28:14.220356'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (765, 'Action-Packed Crime Dramas', '2026-03-03T08:34:52.866238'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (766, 'Action-Comedy Franchises', '2026-03-05T04:56:15.782461'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (767, 'Drama‑focused content', '2026-04-30T07:42:37.602922'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (768, 'Feature-length movies vs TV episodes', '2026-04-29T08:00:24.754795'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (769, 'Epic long‑form sci‑fi/fantasy', '2026-04-29T17:26:43.808612'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (770, 'Action-Adventure Blockbusters Dominate', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (771, 'Documentary Focus / Investigative', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (772, 'Horror/Thriller Emphasis', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (773, 'EPISODE Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (774, 'Genre-Specific Episode Formats', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (775, 'Family Comedy Ensemble”, 8 words or fewer, 1 sentence', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (776, 'Action/Adventure/Spy genre', '2026-05-02T07:52:57.333870'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (777, 'Crime genre presence', '2026-05-01T08:36:29.825696'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (778, 'Modern Variety Show Format', '2026-03-05T05:09:52.085573'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (779, 'Post-Apocalyptic Urban Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (780, 'Character-Driven Ensemble Comedies', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (781, 'War & Historical Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (782, 'Campus-Based Action Series', '2026-03-04T04:41:50.202246'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (783, 'Music-Driven Comedy', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (784, 'Standard hour-long TV episodes', '2026-04-30T07:46:53.284453'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (785, 'Crime Procedurals with Intense Investigation', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (786, 'Family-Focused Entertainment', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (787, 'Curb Your Enthusiasm Comedy Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (788, 'Short comedic adventure TV episodes', '2026-04-29T17:18:48.041717'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (789, 'Animated Family Adventure', '2026-03-04T05:20:56.397393'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (790, 'Animated, Multi-Verse Storytelling', '2026-03-03T05:06:03.804652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (791, 'Space Opera Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (792, 'Light‑hearted episodic content vs serious drama/sci‑fi', '2026-03-06T01:18:59.637896'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (793, 'Comedy Focused / Action Adjacent', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (794, 'Family Adventure Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (795, 'Road‑trip / travel‑focused stories', '2026-04-30T07:41:24.176894'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (796, 'Short-Form, Episodic Focus', '2026-03-04T05:00:15.572854'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (797, 'Drama blended with crime, biography, romance, or children', '2026-03-23T10:41:39.085281'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (798, 'Corporate Excess / Creative Struggle', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (799, 'Franchise Revival - Modern Updates', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (800, 'Sci-Fi Action Blockbusters', '2026-03-04T05:14:50.812175'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (801, 'Sci-Fi Action / Crime Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (802, 'Futuristic or speculative settings versus contemporary realism', '2026-04-27T10:53:19.078563'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (803, 'Mini-Series Focus / Episodic Structure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (804, 'Contemporary real‑world settings vs frontier/sci‑fi settings', '2026-03-20T08:32:18.968558'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (805, 'Crime Dramas with Historical Context', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (806, 'High-Stakes Episodic Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (807, 'Short episodic runtime vs feature-length movies', '2026-05-01T08:23:45.849731'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (808, 'Long-form drama/biography versus short comedy', '2026-04-30T07:38:08.700185'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (809, 'Episode‑only, non‑action titles', '2026-05-02T07:47:35.223983'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (810, 'Wes Anderson-esque Animation & Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (811, 'Horror Mini-Series Emphasis', '2026-03-04T04:53:49.046532'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (812, 'Historical Mini-Series Focus', '2026-03-04T05:19:35.482750'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (813, 'Family-friendly / general audience content', '2026-05-02T07:48:04.765530'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (814, 'Franchise-Driven Family Comedies', '2026-03-03T04:44:58.566431'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (815, 'Feature-length movies vs TV episodes', '2026-03-06T01:20:10.698752'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (816, 'STAR WARS / MANDOLORIAN EPISODES', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (817, 'Documentary Nature Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (818, 'Crime Comedy Contrast', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (819, 'Franchise Driven / Ensemble Cast', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (820, 'Superhero Action Blockbusters Dominate', '2026-03-03T04:48:43.414607'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (821, 'Action-Comedy Franchise', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (822, 'Series episodes vs feature films', '2026-05-01T08:36:01.505882'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (823, 'Genre-Specific Television Series', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (824, 'Action/Sci-Fi vs. Comedy', '2026-03-05T05:01:21.721679'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (825, 'Episode format (short runtime) vs feature film', '2026-03-07T04:48:06.326885'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (826, 'Music Biographies & Crime Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (827, 'Contemporary gritty crime and horror narratives', '2026-03-11T07:05:05.726542'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (828, 'Historical Drama / Political Intrigue', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (829, 'Sci-Fi Action Focus', '2026-03-04T05:17:25.342050'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (830, 'Based on real historical events or figures', '2026-03-06T04:51:52.098466'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (831, 'Adventure or Fantasy genre focus', '2026-03-06T04:56:28.710620'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (832, 'Action/Adventure Focus - Longer Runs', '2026-03-05T05:07:10.280165'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (833, 'Political Espionage & Military Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (834, 'Workplace-centric narratives', '2026-04-28T10:45:58.123276'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (835, 'Darker Tone, Longer Runs', '2026-03-05T05:11:41.280020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (836, 'Franchise Family Comedy', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (837, 'Science‑fiction/action genre‑blended episodes', '2026-03-06T04:41:07.641838'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (838, 'Crime Operatives in Italy', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (839, 'Speculative or supernatural setting', '2026-04-27T01:31:20.672701'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (840, 'Live-action adult drama/comedy (no animation)', '2026-03-06T04:49:43.163403'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (841, 'Non‑Drama genre mix', '2026-05-01T08:21:11.156543'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (842, 'Sci-Fi Action Episode Format', '2026-03-04T04:39:02.545994'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (843, 'Combat‑centric action vs. domestic comedy', '2026-03-06T04:57:35.172618'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (844, 'Animated Family Action Films', '2026-03-04T04:55:09.197744'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (845, 'Crime Family Epic', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (846, 'Light‑hearted genre‑blend episodes', '2026-04-28T10:43:56.951397'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (847, 'Crime‑drama focus', '2026-04-29T09:59:02.789123'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (848, 'Romance-focused storylines', '2026-04-27T10:56:01.737848'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (849, 'Political espionage thriller vs light comedy/fantasy', '2026-03-06T01:19:45.829276'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (850, 'Franchise Pattern - Sitcom Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (851, 'Crime Drama Mini-Series Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (852, 'Nature and travel documentary episodes', '2026-03-06T04:54:48.617667'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (853, 'Darkly Comedic Crime Stories', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (854, 'Serious drama/action tone', '2026-03-09T04:42:33.510550'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (855, 'Action-Focused Cinematic Blockbusters', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (856, 'Crime Thrillers Dominate High', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (857, 'Lighthearted comedy/romance vs serious drama', '2026-03-06T04:45:18.335422'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (858, 'Franchise Driven Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (859, 'Pilot Episode Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (860, '90s Sitcoms vs. Modern Dramas', '2026-03-04T05:05:02.702945'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (861, 'Short TV comedy episodes', '2026-03-19T04:39:39.290251'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (862, 'Historical Drama Focus', '2026-03-05T04:53:14.923687'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (863, 'Crime‑centric stories', '2026-05-01T08:35:46.257032'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (864, 'Episodes featuring History, Fantasy, or Sci‑Fi', '2026-03-09T04:44:20.363477'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (865, 'Contemporary comedy vs period/futuristic drama', '2026-04-29T17:31:56.223402'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (866, 'Multiple episodes from same series', '2026-03-11T07:02:41.031351'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (867, 'Fictional narrative vs documentary nonfiction', '2026-05-02T07:30:34.590517'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (868, 'Music‑focused productions vs crime/drama', '2026-03-07T04:47:51.824485'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (869, 'Crime Drama with Episodic Structure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (870, 'Sci-Fi & Fantasy Focus', '2026-03-04T05:21:48.919711'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (871, 'Crime Thriller - Episodic Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (872, 'Action‑Adventure/Thriller orientation', '2026-04-28T10:42:06.621078'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (873, 'Comedy Ensemble Sitcoms', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (874, 'Spartacus: Ashur Power Dynamics', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (875, 'Contains Crime genre', '2026-04-29T07:51:56.601811'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (876, 'Titles featuring a cast member named Alex', '2026-03-11T04:39:38.179543'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (877, 'High-Budget Action Blockbusters', '2026-03-04T04:53:21.983207'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (878, 'Family Adventure / Holiday', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (879, 'Animated Feature Films', '2026-03-04T04:54:14.885911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (880, 'Nature/Feel‑Good vs Action/Crime Violence', '2026-03-06T04:46:12.375316'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (881, 'Animated Fantasy Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (882, 'Short-Form Crime Thrillers', '2026-03-05T05:15:18.028328'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (883, 'Longer runtime (45+ minutes)', '2026-03-06T01:19:11.844537'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (884, 'Adult drama/comedy content vs children’s comedy', '2026-04-29T17:15:22.175358'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (885, 'Japanese Historical Settings', '2026-03-04T05:18:46.056801'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (886, 'Networked Comedy Situations', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (887, 'Dark Comedy Family Secrets', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (888, 'Midwest Small Town Comedies', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (889, 'Everyday light‑hearted comedy‑drama vs high‑stakes genre', '2026-03-06T01:15:47.640697'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (890, 'Action-Comedy Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (891, 'Darker Tone, Thriller Focus', '2026-03-04T05:15:40.767754'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (892, 'Teen Comedy Focus', '2026-03-03T04:40:19.776513'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (893, 'Animated Family Adventure', '2026-03-04T04:40:01.112331'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (894, 'Crime Films with Long Run Times', '2026-03-05T05:12:08.558728'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (895, 'Action-Focused Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (896, 'High numeric rating (≈9+)', '2026-03-06T04:55:48.559526'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (897, 'Animated Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (898, 'Historical Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (899, 'Standalone Episodic Comedy', '2026-03-04T04:48:52.013290'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (900, 'Dark Comedy Suburban Isolation', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (901, 'EPISODE FORMAT', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (902, 'Comedy/Reality entertainment vs serious drama', '2026-03-07T04:40:13.204924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (903, 'Friends TV Show Dominance', '2026-03-05T05:07:36.804423'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (904, 'Scripted drama/mystery fiction vs nonfiction/comedy reality', '2026-03-11T07:07:55.851176'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (905, 'Includes Mystery genre', '2026-03-06T01:17:45.926633'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (906, 'High-Concept Action / Sci-Fi Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (907, 'Short comedic/drama TV episodes', '2026-03-09T04:41:51.088719'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (908, 'Gritty Action Cinema', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (909, 'Romance genre presence', '2026-03-09T04:41:10.070032'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (910, 'Crime Drama Television Series', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (911, 'Horror/Thriller Small Town Isolation', '2026-03-06T01:12:24.021236'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (912, 'Contemporary dramedy with realistic settings', '2026-04-27T11:09:47.688499'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (913, 'Franchise Reboot / Sequel Fatigue', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (914, 'Fast-Paced, Self-Aware Comedy', '2026-03-05T05:19:49.797947'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (915, 'Based on real people/events', '2026-04-27T11:12:54.668350'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (916, 'High-Budget Crime Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (917, 'Food-Focused Episodic Adventures', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (918, 'Episode-format titles vs non-episode formats', '2026-03-16T04:40:32.236792'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (919, 'Dark Genre Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (920, 'Western Genre Emphasis', '2026-03-05T04:49:59.036830'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (921, 'Real-world contemporary drama (no fantasy/action)', '2026-05-02T07:32:34.611380'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (922, 'Star Trek Exploration & Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (923, 'Franchise or major event specials', '2026-03-06T01:18:27.985754'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (924, 'Short episodic TV vs full-length movies', '2026-03-08T04:46:13.950318'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (925, 'Action and Crime genres present', '2026-03-07T04:50:33.111427'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (926, 'Dark Comedy Ensemble', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (927, 'Crime Drama with Extended Runtime', '2026-03-05T05:16:13.012829'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (928, 'Action-Oriented Westerns', '2026-03-04T05:17:52.184283'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (929, 'Party‑centric social event focus', '2026-03-09T04:42:02.281573'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (930, 'Mainstream drama/comedy without romance or horror', '2026-03-07T08:22:38.361812'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (931, 'Documentary Nature - Short Form', '2026-03-05T05:11:12.886702'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (932, 'Comedy‑heavy genre mix', '2026-04-27T01:25:18.826142'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (933, 'Large-Scale Team Action Sequences', '2026-03-05T05:13:02.502363'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (934, 'Adult live-action drama & documentary', '2026-03-06T04:49:03.950143'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (935, 'Short-Form Episodic Dramas', '2026-03-05T04:46:33.025068'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (936, 'High-Octane Suspense / Thriller', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (937, 'Sci-Fi Action Blockbusters', '2026-03-04T05:20:03.753411'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (938, 'Mythic/Fantasy adventure vs modern comedy', '2026-05-01T08:37:18.698759'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (939, 'High-Concept Genre Television Series', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (940, 'Travelogue Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (941, 'Sci-Fi Space Adventure Focus', '2026-03-05T04:58:27.257229'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (942, 'Romantic Comedy Focus', '2026-03-04T05:04:08.448217'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (943, 'Animated Sci-Fi Adventure', '2026-03-06T01:10:13.582155'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (944, 'It''s Always Sunny Recurring Patterns', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (945, 'Darkly Comedic Suburban Discontent', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (946, 'Action‑Comedy‑Crime blend', '2026-03-16T04:39:39.091041'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (947, 'Action-Adventure Sports Focus', '2026-03-05T05:03:08.914836'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (948, 'Only TV episodes/seasons (no movies)', '2026-03-17T04:39:44.155166'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (949, 'Gossip Girl Era Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (950, 'Comedy‑inclined titles', '2026-03-06T04:43:07.109481'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (951, 'Short‑format comedy sitcom episodes', '2026-03-06T04:52:15.331287'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (952, 'Documentary Music Focus', '2026-03-04T04:55:36.098117'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (953, 'Low critic rating (≤6)', '2026-03-07T04:45:20.934693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (954, 'Comedy‑focused TV episodes', '2026-03-07T04:40:59.348502'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (955, 'Animated Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (956, 'Sci-Fi Action Blockbusters', '2026-03-05T05:14:18.024873'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (957, 'TV episodes (≈45 min) vs feature‑length movies', '2026-03-06T01:17:18.355283'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (958, 'Short-Form Comedy Series', '2026-03-05T04:47:26.765664'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (959, 'Short-Form Episodic Television', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (960, 'Comedy sitcom episodes vs action‑drama movies', '2026-03-07T14:21:37.585750'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (961, 'Action/Drama focus vs Comedy/Documentary focus', '2026-04-27T10:54:59.856322'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (962, 'Western Genre Focus', '2026-03-05T05:04:30.518729'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (963, 'Ongoing series episodes vs standalone films', '2026-04-29T07:54:20.106492'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (964, 'Short-Form Drama Series - Mystery Focus', '2026-03-05T05:05:24.770251'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (965, 'Real-world historical/realistic content vs speculative fiction', '2026-04-28T11:06:58.013925'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (966, 'Features cast members named Alex or Aaron', '2026-05-01T08:29:41.366444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (967, 'Recent single‑episode TV (short, non‑historical)', '2026-03-10T04:41:45.315070'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (968, 'Crime‑focused titles', '2026-03-06T04:54:19.400360'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (969, 'Sci-Fi Action Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (970, 'Supernatural or speculative premise', '2026-04-27T10:41:57.687652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (971, 'Animated Episodic Comedy', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (972, 'Small-Town Ensemble Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (973, 'Contemporary Romance & Competition', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (974, 'Feature-length movies vs TV episodes', '2026-03-13T04:40:15.067012'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (975, 'Mystery Adventure Series', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (976, 'Western Action Genre Blend', '2026-03-04T04:48:24.706438'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (977, 'Dark Comedy Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (978, 'Crime‑drama focus versus comedy/action focus', '2026-03-06T01:21:22.652204'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (979, 'Comedy/light tone vs dark mystery/thriller', '2026-04-27T01:35:38.551818'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (980, 'Adventure/sci‑fi franchise focus', '2026-04-28T10:55:07.950804'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (981, 'Long‑form drama/action episodes', '2026-04-29T17:22:15.271238'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (982, 'Financial Crime Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (983, 'Comedy‑heavy titles vs non‑comedy dramas', '2026-03-06T04:50:45.108495'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (984, 'Grounded realistic narratives', '2026-03-08T04:45:26.125410'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (985, 'Past historical settings', '2026-04-29T08:07:52.232033'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (986, 'TV episodes vs. movies', '2026-05-02T07:44:31.861369'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (987, 'Dark Comedy Crime”, “explanation”: “These items feature darkly comedic crime narratives with a focus on morally question', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (988, 'Serious drama episodes vs comedic sitcom episodes', '2026-03-06T01:21:09.314398'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (989, 'Short-Form Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (990, 'Animated Family Adventure', '2026-03-04T04:43:58.443740'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (991, 'Genre-Specific Production Values', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (992, 'Comedy‑dominant with adventure or crime elements', '2026-03-11T04:41:32.829414'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (993, 'Feature-length movies vs TV episodes', '2026-03-07T04:45:35.127723'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (994, 'Contains Drama genre', '2026-04-27T11:11:18.777416'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (995, 'Action-Adventure Blockbusters', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (996, 'Action/Sci‑Fi focus vs Comedy focus', '2026-03-09T04:41:36.550322'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (997, 'Historical Drama / Sci-Fi', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (998, 'Comedy-focused TV episodes under hour', '2026-03-06T01:17:03.798162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (999, 'Feature films present vs episode‑only', '2026-03-07T08:23:46.816226'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1000, 'Non‑action/Adventure episodes', '2026-03-07T04:48:37.311203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1001, 'Long-form action/adventure movies vs short comedy episodes', '2026-05-01T08:33:40.068826'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1002, 'Action‑Adventure / Multi‑genre titles vs Straight Drama', '2026-03-07T14:22:29.714060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1003, 'Comedy‑rich titles', '2026-03-07T14:18:25.081078'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1004, 'Sci-Fi/Action vs. Comedy', '2026-03-05T05:18:00.996911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1005, 'Travel Documentary Series', '2026-03-03T04:58:55.533212'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1006, 'Animated Episodic Action', '2026-03-05T05:17:34.264310'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1007, 'Standard half‑hour episode length', '2026-03-07T04:43:12.974495'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1008, 'Political‑espionage TV episodes vs other media', '2026-05-01T08:37:05.560971'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1009, 'Specific episode titles vs generic season labels', '2026-04-27T01:29:29.975419'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1010, 'Predominantly Action/Adventure titles', '2026-03-07T14:15:33.145938'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1011, 'Genre-Driven Action Dramas', '2026-03-05T04:45:16.939940'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1012, 'Short TV episodes vs full-length movies', '2026-03-06T04:48:33.082828'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1013, 'Serious adult‑oriented narratives', '2026-04-30T07:35:47.229169'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1014, 'TV episodes versus feature films', '2026-03-10T04:44:25.206852'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1015, 'High-Contrast Music Performances', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1016, 'Documentary Focus / Concert Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1017, 'Action‑Adventure/Fantasy focus vs Drama‑Crime focus', '2026-04-29T07:46:33.699951'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1018, 'Crime Comedies with Episodic Structure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1019, 'Genre-Specific Franchise Patterns', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1020, 'Action‑Adventure focus', '2026-03-06T04:55:32.742739'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1021, 'High‑concept frontier or sci‑fi adventure', '2026-03-11T07:04:18.894594'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1022, 'Longer, non‑comedic feature/episode vs short sitcom', '2026-04-29T09:44:50.296955'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1023, 'High-Concept Comedy with Ensemble Casts', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1024, 'Lighthearted family adventure/comedy', '2026-03-07T04:46:13.042915'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1025, 'Travel-Based Action Comedies', '2026-03-04T04:57:45.895392'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1026, 'Speculative/fantasy genre emphasis', '2026-04-27T10:47:45.347874'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1027, 'High-Octane Action with Ensemble Casts', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1028, 'Mostly TV episode titles', '2026-03-08T04:45:51.045411'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1029, 'Whimsical Genre Blend', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1030, 'Reality TV / Game Show Dominance', '2026-03-03T05:18:58.955631'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1031, 'Short-Form Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1032, 'Drama‑centric, serious tone', '2026-03-08T04:40:47.413584'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1033, 'Animated Action Series Focus', '2026-03-04T05:11:40.777561'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1034, 'Features an actor named Adam', '2026-03-07T04:43:40.471634'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1035, 'Historical Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1036, 'Comedy Television Series', '2026-03-04T05:21:22.340185'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1037, 'Grounded drama/comedy vs speculative action/fantasy', '2026-04-29T08:00:10.935971'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1038, 'Reality TV & Comedy Focus', '2026-03-04T04:52:07.075315'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1039, 'Franchise Pattern - Established Teams', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1040, 'Futuristic sci‑fi / dystopian settings', '2026-03-11T04:41:44.275068'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1041, 'Contemporary real‑world stories', '2026-05-02T07:54:20.160291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1042, 'Comedy Focus - Short Form', '2026-03-04T05:01:39.833368'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1043, 'lighter, comedic or optimistic tone', '2026-03-11T04:41:16.517181'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1044, 'Crime Procedural Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1045, 'Biographical Limited Series', '2026-03-04T04:40:58.103308'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1046, 'Crime Drama Mini-Series Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1047, 'Travel Documentary Series', '2026-03-04T05:05:55.943074'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1048, 'Documentary/Sci-Fi Hybrid', '2026-03-04T05:22:15.655924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1049, 'Short TV episodes (≤50 min) vs longer formats', '2026-04-28T10:44:56.360892'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1050, 'Animated Episodic Comedy', '2026-03-06T01:08:51.663448'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1051, 'Standalone TV episodes vs movies/season collections', '2026-03-13T04:40:45.382271'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1052, 'Prestige TV drama episodes non‑franchise', '2026-03-07T04:44:09.033836'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1053, 'Short episode runtimes', '2026-04-28T10:44:26.184080'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1054, 'Sci-Fi Action with High Production Values', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1055, 'Comedy/Reality episodes versus serious drama series', '2026-03-09T04:40:31.109439'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1056, 'Large-Scale Action Blockbusters', '2026-03-04T05:10:50.673323'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1057, 'TV episode (short runtime) vs feature film', '2026-03-07T04:51:16.423899'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1058, 'Genre-Driven Action/Adventure Focus', '2026-03-04T04:51:18.076364'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1059, 'Sci-Fi/Action Survival', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1060, 'Modern Episodic Formats', '2026-03-05T04:46:06.496940'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1061, 'Crime genre vs non‑crime titles', '2026-04-28T11:02:24.261532'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1062, 'Animated Episodic Entertainment', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1063, 'Action-Focused Crime Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1064, 'Romantic/comedic domestic stories', '2026-03-06T01:17:33.802892'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1065, 'Action‑heavy franchise titles vs modest drama', '2026-03-07T14:22:04.123699'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1066, '{', '2026-03-05T05:08:56.670471'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1067, 'Investigation‑focused crime/mystery titles', '2026-03-07T14:23:47.912024'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1068, 'Animated Shorts vs. Feature Films', '2026-03-04T05:06:24.689648'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1069, 'Personal/family relationship‑driven drama', '2026-03-06T04:54:37.735451'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1070, 'Crime Business Operations', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1071, 'Serious drama/action titles vs light romance/comedy', '2026-05-01T08:39:17.483647'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1072, '≤60‑minute TV episodes vs feature‑length films', '2026-04-29T08:01:37.144176'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1073, 'Female‑lead narratives', '2026-03-06T04:39:46.729358'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1074, 'Starts with “The”', '2026-03-06T04:47:06.742910'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1075, 'Dark Crime Procedurals with Episodic Structure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1076, 'Contemporary live-action vs fantastical/speculative settings', '2026-03-07T04:46:56.257305'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1077, 'Action‑genre emphasis versus comedy‑drama focus', '2026-03-11T04:39:22.452307'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1078, 'Family‑oriented adventure vs gritty action/history', '2026-03-14T04:41:16.052266'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1079, '30‑minute‑plus episodes and feature‑length films', '2026-03-07T04:42:43.157225'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1080, 'Crime Procedurals with Female Leads', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1081, 'Light‑hearted comedy/Reality vs serious action drama', '2026-03-08T04:43:00.016570'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1082, 'High-Octane Action Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1083, 'Includes Science Fiction genre', '2026-03-08T04:43:15.358682'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1084, 'Big Screen Concert Experiences', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1085, 'Historical War Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1086, 'TV sci‑fi anthology episodes vs standalone movies', '2026-03-06T01:15:17.090888'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1087, 'Personal/biographical drama over action spectacle', '2026-03-07T14:22:16.699171'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1088, 'Action-Comedy Episodic Focus', '2026-03-04T05:00:42.373566'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1089, 'Non‑comedic adult drama', '2026-03-13T04:42:12.520533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1090, 'Horror/Thriller Emphasis', '2026-03-05T05:12:35.625183'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1091, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1092, 'High-Budget Sci-Fi & Mystery', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1093, 'Teen romance‑mystery episode', '2026-03-06T04:40:37.079787'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1094, 'Modern contemporary setting vs historical/period setting', '2026-03-10T04:44:10.103873'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1095, 'Live‑action comedy‑drama TV episodes', '2026-03-06T04:44:52.494410'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1096, 'Sci-Fi Horror with Extended Runs', '2026-03-05T05:20:44.756855'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1097, 'Animated Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1098, 'Crime Thriller Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1099, 'Mini-Series / Short Form', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1100, 'Standalone drama TV episodes (~45‑minute runtime)', '2026-03-06T04:41:57.307765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1101, 'Mystery / Science‑Fiction focus', '2026-04-28T10:57:42.077659'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1102, 'Family-friendly adventure/comedy vs adult crime drama', '2026-03-07T14:19:04.824423'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1103, 'Long dramatic/genre titles vs short sitcom episodes', '2026-03-06T04:46:53.611654'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1104, 'Star Trek Universe - Exploration & Conflict', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1105, 'Dark Comedy Crime', '2026-03-05T05:13:51.387999'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1106, 'Comedy/Family tone versus horror/thriller tone', '2026-04-28T11:06:21.035260'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1107, 'Comedy‑driven franchise installments', '2026-03-25T10:42:16.757555'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1108, 'Documentary Focus / Natural History', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1109, 'Format/Franchise Pattern', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1110, 'High-Budget Production Values', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1111, 'Comedy‑centric short episodes vs non‑comedy longer formats', '2026-03-07T04:45:01.600959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1112, 'Sport-Focused Character Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1113, 'Animated Comedy vs. Live-Action Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1114, 'Darkly Comedic Crime Investigations', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1115, 'TV episode format', '2026-03-06T04:53:47.212249'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1116, 'Action‑Adventure emphasis vs pure drama', '2026-03-06T04:47:52.462633'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1117, 'Genre-Driven Franchise Patterns', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1118, 'Standalone titles vs sitcom season bundles', '2026-03-08T04:45:36.860672'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1119, 'Adult‑oriented vs Children‑focused', '2026-03-17T04:39:59.832848'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1120, 'Includes fantasy, documentary, or animation genre', '2026-03-10T04:41:28.130872'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1121, 'Family-Focused Comedy', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1122, 'Drama‑focused TV episodes', '2026-03-11T04:40:24.634253'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1123, 'Documentary/Drama focus versus Action/Adventure focus', '2026-03-06T04:52:45.177791'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1124, 'Franchise Superhero Content', '2026-03-05T04:49:09.192430'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1125, 'Crime Drama with Extended Runs', '2026-03-04T05:13:02.824300'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1126, 'Pure drama titles vs mixed‑genre comedy/horror/sci‑fi', '2026-03-24T10:42:26.655261'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1127, 'Comedy‑centric vs Action/Adventure/Horror', '2026-03-06T01:18:42.920506'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1128, 'Drama‑centric TV episodes', '2026-03-24T10:41:55.779634'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1129, 'High-Concept, Character-Driven Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1130, 'Crime Dramas with Extended Runs', '2026-03-04T05:10:23.783597'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1131, 'Action-Adventure Franchises Dominate', '2026-03-06T01:06:55.286379'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1132, 'Lighthearted Comedy vs Dark Horror', '2026-04-29T07:58:47.160657'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1133, 'Action-Focused, Fast-Paced Storytelling', '2026-03-04T04:46:58.509989'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1134, 'Sci-Fi Action / Comedy Blend', '2026-03-05T04:54:59.582124'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1135, 'Mystery‑or‑Sci‑Fi genre titles', '2026-03-09T04:43:47.192374'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1136, 'Character-Driven Crime Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1137, 'Comedy‑Adventure focus vs Crime‑Drama focus', '2026-03-14T04:40:26.658805'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1138, 'Sitcom Episode Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1139, 'Short sitcom episodes vs long dramatic hour‑long', '2026-03-08T04:45:15.225101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1140, 'Short‑form TV episodes vs long‑form blockbuster movies', '2026-03-11T07:04:49.298997'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1141, 'Franchise tie‑in episodes vs standalone titles', '2026-05-02T07:47:08.067606'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1142, 'Comedy-Focused Television Series', '2026-03-05T04:54:07.193791'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1143, 'Aaron in cast', '2026-03-07T14:18:51.171786'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1144, 'Darker Tone & Action Focus', '2026-03-04T05:08:38.026242'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1145, 'Light‑hearted genre‑mix vs serious drama', '2026-03-08T04:41:20.212706'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1146, 'Adventure/Fantasy genre', '2026-03-11T07:03:25.598927'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1147, 'Feature films vs TV episodes', '2026-03-06T04:50:33.545666'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1148, 'Scripted crime/drama vs nonfiction travel/documentary', '2026-03-12T08:20:01.373309'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1149, 'Includes Action genre', '2026-03-07T04:39:58.417197'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1150, 'Action-Adventure Blockbusters', '2026-03-06T01:13:18.697325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1151, 'Action-Oriented vs. Family-Focused', '2026-03-05T05:09:24.531972'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1152, 'Sci‑Fi/Fantasy & Superhero titles', '2026-03-08T04:46:27.334257'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1153, 'Contains Drama genre', '2026-03-06T04:40:08.387217'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1154, 'Dark Mystery Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1155, 'Short comedic episodes vs longer serious dramas', '2026-03-12T08:20:15.814348'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1156, 'Short-Form Action Dramas', '2026-03-04T05:07:17.688964'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1157, 'Episode format vs feature film', '2026-04-29T17:22:35.719279'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1158, 'TV episode format vs feature film', '2026-03-07T04:48:53.065200'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1159, 'Action‑driven, speculative or competitive settings', '2026-03-14T04:41:00.634620'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1160, 'Treasure‑hunting adventure titles', '2026-03-09T04:42:46.197281'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1161, 'TV drama/episodic vs action‑adventure movies', '2026-03-07T04:46:38.362421'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1162, 'Comedy titles lacking crime elements', '2026-03-07T04:44:28.833381'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1163, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1164, 'Lighthearted comedy vs dark thriller/horror', '2026-03-07T04:49:51.884959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1165, 'Long-Form Series Focus', '2026-03-05T04:55:53.301337'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1166, 'Long-Form Drama Series', '2026-03-04T05:22:44.902826'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1167, 'Mystery/Thriller Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1168, 'Scripted fiction vs unscripted reality TV', '2026-03-08T04:46:04.204826'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1169, 'Comedy Sitcom vs. Blockbuster Action', '2026-03-05T05:15:45.505352'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1170, 'Crime/Action Thriller Emphasis', '2026-03-07T04:41:15.563754'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1171, 'Standalone productions vs multi‑episode seasons', '2026-04-30T07:44:04.176070'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1172, 'Action‑focused episodes (often with Crime/Comedy)', '2026-04-29T10:01:00.099321'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1173, 'Modern Crime Dramas', '2026-03-05T05:19:22.402316'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1174, 'Contains Drama genre', '2026-03-06T01:16:06.216957'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1175, 'Adventure‑Drama TV Episodes', '2026-03-13T04:41:54.658792'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1176, 'Speculative genre fiction vs realistic grounded drama', '2026-04-30T07:47:12.349920'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1177, 'Genre-Driven Action & Sci-Fi', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1178, 'Superhero/Fantasy source material vs grounded realism', '2026-03-06T04:43:40.940091'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1179, 'Franchise‑linked titles vs non‑franchise episodes', '2026-03-18T04:40:00.917221'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1180, 'Musical Variety / Travelogue', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1181, 'Animated Family Blockbusters', '2026-03-03T04:48:15.142298'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1182, 'Absence of horror or sci‑fi genres', '2026-03-20T08:31:06.941944'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1183, 'Marvel Cinematic Universe Focus', '2026-03-05T04:46:59.635899'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1184, 'Science Fiction / Mystery Focus', '2026-03-04T05:16:36.046040'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1185, '80s/90s Action Comedy', '2026-03-05T05:05:53.571173'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1186, 'Live-action TV episodes vs animated movies', '2026-03-20T04:39:25.080288'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1187, 'Star Trek Exploration vs. Procedural Crime', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1188, 'Travel Documentary Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1189, 'Episode‑only titles vs feature‑film titles', '2026-03-21T04:40:04.588162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1190, 'Short-Form Episodic Dramas', '2026-03-05T04:40:53.105477'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1191, 'Comedy‑drama TV episodes', '2026-05-02T07:48:54.635155'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1192, 'Titles featuring an actor named Adrian', '2026-03-06T01:20:56.138529'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1193, 'Low-Stakes Comedy / Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1194, 'Action-Adventure Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1195, 'Comedy‑centric titles', '2026-03-07T04:47:09.750996'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1196, 'Animated Action Sci-Fi', '2026-03-05T05:10:44.831878'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1197, 'Live‑action crime/drama TV episodes', '2026-03-06T01:14:14.035067'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1198, 'Genre-Specific Franchise Patterns', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1199, 'Character‑driven TV episodes vs spectacle‑driven movies', '2026-03-11T07:06:19.263428'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1200, 'Sports-Focused Comedy Contrast', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1201, 'Short-Form Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1202, 'Animated Action Blockbusters', '2026-03-04T05:09:29.230286'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1203, 'Action/Adventure or Fantasy genre', '2026-03-07T04:47:39.465634'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1204, 'Music‑focused light comedy vs serious drama', '2026-03-13T04:41:10.162330'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1205, 'Networked Episodic Television Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1206, 'Music Focused Entertainment', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1207, 'Short children’s comedy episodes vs adult long-form drama', '2026-03-06T04:49:55.352819'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1208, 'Action-Focused Military/Thriller', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1209, 'Light, animated or comedic adventure vs serious drama', '2026-03-06T04:48:08.143702'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1210, 'Animated Musical vs. Serious Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1211, 'Adventure Family Genre Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1212, 'Crime Procedurals with Intense Investigation', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1213, 'Crime Dramas with Long Run Times', '2026-03-05T05:08:03.500706'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1214, 'Adult crime/drama emphasis vs family/genre‑specific titles', '2026-04-29T09:57:40.303463'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1215, 'Crime/Drama/Action focus vs pure comedy', '2026-04-28T10:54:49.928400'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1216, 'Short TV episodes vs long-form movies', '2026-03-07T04:46:00.425564'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1217, 'Mature live-action titles', '2026-03-07T14:19:23.813484'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1218, 'Standalone film/anthology episode vs serialized series episode', '2026-04-29T08:01:18.642806'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1219, 'Romantic Comedies with Ensemble Casts', '2026-03-04T05:04:34.331802'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1220, 'Comedy TV Seasons', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1221, 'Franchise Pattern: Established Teams', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1222, 'Live-action scripted series episodes', '2026-03-07T14:15:11.826276'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1223, 'Action-Focused Sci-Fi/Horror', '2026-03-05T05:18:27.656979'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1224, 'Short TV episodes vs full-length movies', '2026-03-07T04:42:26.958197'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1225, 'Comedy‑drama vs serious drama/mystery', '2026-03-07T04:39:41.587796'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1226, 'Military Action / Crisis Response', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1227, 'Comedy‑focused titles vs serious drama', '2026-04-29T09:50:17.622547'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1228, 'High-Budget Action vs. Low-Budget Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1229, 'Documentary vs. Feature Film', '2026-03-04T05:12:35.009094'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1230, 'Genre-Specific Production Values', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1231, 'Real‑world subject focus (documentary/biography)', '2026-03-11T04:40:09.776161'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1232, 'Standalone titles vs full-season series', '2026-03-07T14:17:08.789616'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1233, 'Contemporary modern‑day settings', '2026-03-07T14:22:46.895539'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1234, 'Sci-Fi Action Series', '2026-03-04T04:52:34.042919'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1235, 'Crime Dramas with Extended Runs', '2026-03-04T04:45:18.929117'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1236, 'Biographical Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1237, 'Dark Genre Focus / Horror Emphasis', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1238, 'Big‑budget mainstream action/adventure titles', '2026-03-07T04:51:49.065639'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1239, 'Animated Series vs. Live-Action', '2026-03-03T04:56:49.997937'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1240, 'Speculative genre (Sci‑Fi/Horror)', '2026-03-06T04:43:28.105042'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1241, 'Franchise Pattern - Recurring Characters', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1242, 'Hour‑long drama episodes vs short/comedy or film', '2026-03-07T04:44:47.803325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1243, 'Crime genre presence', '2026-04-27T11:10:25.653072'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1244, 'Predominantly comedic tone', '2026-03-06T04:57:21.848347'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1245, 'Crime Drama Series', '2026-03-05T05:02:42.448774'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1246, 'Documentary Nature Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1247, 'Half‑hour sitcom episodes vs hour‑long sci‑fi', '2026-03-06T04:46:38.192384'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1248, 'Feature-length high-rated titles vs short comedy episodes', '2026-03-07T14:15:51.982765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1249, 'Animated Food Adventures', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1250, 'Drama or crime/mystery genre presence', '2026-03-09T04:40:55.569694'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1251, 'Historical Drama Focus', '2026-03-04T04:44:25.982608'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1252, 'Western Setting & Long Runtime', '2026-03-05T04:42:42.040178'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1253, 'Drama-focused longer-format productions vs short comedies', '2026-03-07T14:20:38.109778'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1254, 'Grounded real-world drama and biography', '2026-03-07T04:49:27.021562'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1255, 'Action-Comedy with Ensemble Casts', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1256, 'Genre-Specific Character Comedies', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1257, 'Action-Adventure Focus on Sci-Fi', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1258, 'Taylor Swift Tour Documentation', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1259, 'Action-Comedy Genre Blend', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1260, 'Short comedy sitcom episodes vs long dramatic titles', '2026-03-08T04:43:53.754851'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1261, 'Predominantly comedy‑oriented titles', '2026-04-30T07:49:17.241274'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1262, 'Comedy Series vs. Action Movies', '2026-03-04T04:47:28.287389'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1263, 'Genre-Specific Ensemble Comedies', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1264, 'Adventure/Action genre titles', '2026-04-29T09:56:12.315433'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1265, 'British‑directed productions', '2026-03-06T01:27:10.669856'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1266, 'Half‑hour live‑action comedy episodes', '2026-03-07T04:50:44.336053'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1267, 'Profession‑focused narratives', '2026-03-23T10:42:36.833842'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1268, 'Includes documentary genre', '2026-03-25T10:41:31.047090'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1269, 'Original/standalone titles vs franchise-linked titles', '2026-03-07T08:23:13.257342'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1270, 'Romance‑centric stories vs action/irreverent comedy', '2026-03-08T04:42:35.223688'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1271, 'Crime‑Drama focus vs Action‑Adventure focus', '2026-03-08T04:43:43.842055'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1272, 'Crime Drama with Shorter Runs', '2026-03-05T04:50:26.444134'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1273, 'Action‑driven TV episodes vs non‑action biopics', '2026-03-06T04:42:49.019825'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1274, 'Comedy‑Drama genre blend', '2026-03-07T04:47:25.975443'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1275, 'Crime Drama with Recurring Conflicts', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1276, 'Crime Drama Focus on Action Sequences', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1277, 'Rural/Western land‑based settings', '2026-03-12T08:20:28.071649'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1278, 'Contemporary real-world drama', '2026-04-27T11:03:18.709407'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1279, 'Action‑Adventure/Fantasy vs Teen Romance‑Mystery', '2026-03-15T04:39:47.212568'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1280, 'anti‑establishment critique', '2026-03-07T14:17:40.110302'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1281, 'Standalone titles vs episode subtitles', '2026-05-02T07:49:28.401746'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1282, 'Action-Thriller Episodic Format', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1283, 'Action‑Adventure episodes with 50‑minute runtimes', '2026-03-06T04:53:31.560090'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1284, 'Television Series - Comedy Focus', '2026-03-03T04:45:24.383233'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1285, 'Mixed‑genre TV series (comedy/fantasy)', '2026-05-01T08:29:05.020284'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1286, 'Feature-length movies versus short TV episodes', '2026-03-06T04:43:54.712592'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1287, 'Non‑crime titles vs crime‑focused episodes', '2026-04-29T07:51:38.054853'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1288, 'Genre-Driven Adventure vs. Domestic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1289, 'High-Concept Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1290, 'Documentary Food Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1291, 'Horror Focus - Late Night', '2026-03-05T04:43:35.137913'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1292, 'Big‑budget franchise films vs TV episode content', '2026-03-10T04:43:49.296013'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1293, 'Animated Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1294, 'Dark Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1295, 'FX It''s Always Sunny Seasons', '2026-03-05T05:02:16.319517'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1296, 'Drama paired with non‑crime genre blends', '2026-04-27T10:52:26.462813'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1297, 'Non‑drama primary genre blend vs. pure drama focus', '2026-04-29T17:27:22.563710'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1298, '80s Setting / Tone', '2026-03-04T04:54:42.729356'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1299, 'Action/Crime drama versus light comedy', '2026-03-12T08:19:29.746248'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1300, 'Short-Form Comedy Series', '2026-03-05T04:51:21.925318'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1301, 'Fictional scripted stories vs documentary nonfiction', '2026-03-06T04:53:00.531520'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1302, 'Short sitcom episodes vs long drama episodes', '2026-05-01T08:20:27.889961'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1303, 'Legacy franchise episodes vs new series episodes', '2026-03-08T04:42:08.161009'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1304, 'Horror/Thriller Focus', '2026-03-05T04:48:20.111594'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1305, 'Comedy‑focused vs serious action/drama', '2026-03-07T14:16:05.870524'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1306, 'High-Budget Action/Thriller Focus', '2026-03-06T01:09:19.995271'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1307, 'Serious drama & sci‑fi vs comedy/fantasy', '2026-03-06T04:38:59.229086'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1308, 'Quentin Tarantino-Era Films', '2026-03-05T05:04:02.569188'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1309, 'Sitcom‑style comedy vs serious drama/crime', '2026-03-06T04:56:15.086087'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1310, 'Feature-length movies vs TV episodes', '2026-03-06T01:15:33.056433'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1311, 'Short comedic TV sitcom episodes', '2026-04-01T10:42:07.117229'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1312, 'Short-Form Episodic Content', '2026-03-05T04:53:41.809185'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1313, 'Contains Comedy genre tag', '2026-03-08T04:43:32.636087'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1314, 'Horror/Thriller Focus – Shorter Runs', '2026-03-04T04:56:02.825795'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1315, 'Comedy‑centric productions vs serious dramas', '2026-03-06T04:55:21.215306'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1316, 'Regular series episodes (non‑pilot)', '2026-03-07T14:22:59.549937'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1317, 'Nostalgic 80s Film Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1318, 'Music-Driven Comedy Reboots', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1319, 'Short-form TV episodes vs feature-length movies', '2026-04-29T17:12:45.229475'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1320, 'Franchise Pattern: Established Continuity', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1321, 'TV episodes (short runtime) vs feature films', '2026-03-07T04:52:00.584911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1322, 'Action-Comedy Genre Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1323, 'Musical Biographies & Historical Context', '2026-03-06T01:10:41.640078'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1324, 'Serious drama and documentary genres', '2026-03-09T04:44:36.964709'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1325, 'Documentary & Nature Soundscapes', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1326, 'Dark genre (horror/crime) vs light comedy/animation', '2026-03-07T14:18:38.731021'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1327, 'Animal Observation Documentaries', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1328, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1329, 'Feature-length movies vs short TV episodes', '2026-03-09T04:40:15.512406'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1330, 'Speculative genre (sci‑fi/horror) vs realistic drama', '2026-03-06T04:46:26.002665'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1331, 'Sci‑fi or speculative full‑length productions', '2026-03-13T04:40:58.166523'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1332, 'Non‑crime titles', '2026-03-06T01:19:59.790810'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1333, 'Feature films vs short TV episodes', '2026-03-15T04:40:17.431910'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1334, 'Short-Form Episodic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1335, 'Crime Family Power Struggles', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1336, 'Franchise Pattern: Superhero Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1337, 'Contemporary comedy‑drama TV episodes', '2026-04-29T08:02:49.957122'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1338, 'High-Budget Studio Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1339, 'Everyday contemporary settings vs high‑concept fantasy/action', '2026-03-08T04:41:35.031763'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1340, 'Live Concert Performances', '2026-03-04T05:18:18.941616'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1341, 'Action vs. Character-Focused', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1342, 'High-Octane Action & Crisis', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1343, 'Fantasy/Period genre blends vs contemporary sitcom', '2026-03-11T07:02:11.705600'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1344, 'Action-Comedy Contrast', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1345, 'Animated Comedy Series', '2026-03-05T05:06:43.072589'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1346, 'Action‑thriller / political drama vs light comedy', '2026-03-12T08:21:26.448579'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1347, 'Dark Comedy Tone', '2026-03-05T04:52:46.932003'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1348, 'Contains Comedy or Music genre tag', '2026-03-15T04:40:48.862672'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1349, 'Standalone scripted TV episodes', '2026-03-15T04:39:13.065086'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1350, 'High-Budget Sci-Fi Action', '2026-03-05T05:10:18.409440'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1351, 'Animated Family Focus', '2026-03-05T04:44:50.977186'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1352, 'Short-Form Comedy Series', '2026-03-04T04:46:08.373364'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1353, 'High-Octane Racing vs. Domestic Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1354, 'Long-form action/adventure or music documentary', '2026-03-11T04:42:06.969072'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1355, 'Documentary Travel / Adventure', '2026-03-04T05:13:29.326137'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1356, 'Recurring Diplomat Series', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1357, 'Comedy‑oriented titles vs serious drama', '2026-03-11T07:06:39.174319'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1358, 'Marvel vs. Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1359, 'Crime Family Dramas', '2026-03-05T04:41:46.773315'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1360, 'Animated Family Comedies', '2026-03-05T04:51:49.543130'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1361, 'Niche limited series & low‑budget films', '2026-04-29T17:19:31.158335'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1362, 'High‑intensity genre (Sci‑Fi, Action, Crime)', '2026-03-07T14:20:54.097876'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1363, 'Children''s Animated Comedy Focus', '2026-03-04T04:44:52.276083'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1364, 'Adventure/Action‑Comedy entertainment episodes', '2026-05-01T08:35:05.096376'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1365, 'TV episodes versus feature films', '2026-04-27T10:59:47.128103'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1366, 'Thriller/Horror genre presence', '2026-03-08T04:42:46.631589'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1367, 'High-Concept Adventure / Historical Return', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1368, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1369, 'Family-Focused Drama Series', '2026-03-04T05:14:23.560567'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1370, 'Crime Dramas with Complex Plots', '2026-03-05T04:50:54.054286'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1371, 'Animated Children''s Entertainment', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1372, 'Pre‑2010 releases', '2026-03-10T04:42:05.182693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1373, 'Drama genre presence vs pure comedy', '2026-03-10T04:43:04.338767'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1374, 'Action‑Adventure/Crime emphasis', '2026-03-07T14:20:07.515141'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1375, 'Satirical Comedy Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1376, 'Music Focused vs. Narrative Driven', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1377, 'Episode format vs season format', '2026-03-20T04:40:28.280846'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1378, 'Historical crime drama vs modern comedy', '2026-03-07T04:43:25.476673'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1379, 'Short standalone episodes vs longer season blocks', '2026-03-10T04:40:48.167865'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1380, 'Includes Crime genre', '2026-04-28T10:58:51.351807'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1381, 'Musical Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1382, '{', '2026-03-05T05:14:48.351032'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1383, 'Hour‑plus runtimes vs sub‑hour episodes', '2026-03-07T04:48:19.774858'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1384, 'Historical Drama with Extended Runtime', '2026-03-03T04:43:42.853075'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1385, 'Comedy‑drama TV episodes vs Action‑adventure movies', '2026-04-30T07:44:40.743833'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1386, 'Short-Form Episodic Horror', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1387, 'Short‑format sitcom romance episodes', '2026-03-08T04:44:23.797408'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1388, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1389, 'Critically acclaimed scripted drama/adventure titles', '2026-03-11T07:04:06.442924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1390, 'Historical War Dramas', '2026-03-05T04:56:44.053627'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1391, 'Romance/comedy focus vs serious genre titles', '2026-03-11T07:07:13.767434'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1392, 'Large-Scale Action Blockbusters', '2026-03-05T04:47:54.095636'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1393, 'Adult drama/fantasy content vs child comedy', '2026-03-10T04:42:32.578717'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1394, 'Comedy‑heavy TV episodes vs serious movies', '2026-03-07T14:16:19.808056'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1395, 'Action-Oriented, High-Budget Production', '2026-03-04T04:42:41.108406'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1396, 'Action-Oriented Sci-Fi Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1397, 'Drama‑centric TV episodes', '2026-03-29T08:55:55.726404'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1398, 'Musical Family Dynamics', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1399, 'Short comedic TV episodes vs long action dramas', '2026-03-06T04:44:23.474326'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1400, 'Crime Drama Mini-Series Focus', '2026-03-06T01:09:46.916938'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1401, 'Longer Runtime / Action Focus', '2026-03-05T04:52:19.578397'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1402, 'Historical Biographical Dramas', '2026-03-04T04:58:14.327466'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1403, 'Character-Driven Ensemble Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1404, 'Animated Family Focus', '2026-03-05T05:18:54.499496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1405, 'High‑profile director involvement', '2026-03-12T08:21:13.874394'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1406, 'Migration-themed or planetary crisis titles', '2026-03-07T04:51:01.301372'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1407, 'Dark Mystery Crime', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1408, 'Adult‑focused gritty narratives vs family/teen light fare', '2026-03-07T04:39:11.835337'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1409, 'Supernatural/fantasy genre', '2026-03-09T04:40:42.679203'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1410, 'Scripted series episodes vs. movies/documentary', '2026-03-11T07:06:02.077264'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1411, 'Serious drama/sci‑fi episodes (vs comedy)', '2026-03-09T04:41:24.401329'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1412, 'Historical Dramas with Military Focus', '2026-03-06T01:12:51.758072'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1413, 'Comedy vs. Action-Adventure', '2026-03-03T05:05:36.099128'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1414, 'Drama‑centric titles', '2026-03-06T01:15:05.462648'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1415, 'Action/genre‑drama blend vs pure comedy episodes', '2026-03-21T04:40:38.049222'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1416, 'Documentary & Historical Exploration', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1417, 'Character-Driven Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1418, 'Fantasy/Sci‑Fi/Animation content', '2026-03-06T04:42:30.708962'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1419, 'Animated Adventure vs. Crime Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1420, 'Character-Driven Mystery Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1421, 'Mini-Series / Episodes Focus on Drama', '2026-03-05T04:44:23.868790'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1422, 'Long-form action/adventure movies vs short comedy episodes', '2026-04-27T01:26:26.358673'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1423, 'Animated Action Series Dominance', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1424, 'Mission‑driven high‑stakes thriller', '2026-03-08T04:39:12.286871'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1425, 'Recent low‑rated comedy‑crime/action episodes', '2026-03-07T04:41:28.339719'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1426, 'Family-Focused Entertainment', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1427, 'Hospital-Based Medical Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1428, 'Short episodic TV crime dramas vs feature films', '2026-03-31T10:41:55.609907'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1429, 'Short-form TV episodes (under hour)', '2026-03-07T08:24:09.707193'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1430, 'High-Concept Thriller / Horror', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1431, 'Animated Family Films', '2026-03-04T04:47:57.526351'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1432, 'Serious adult drama episodes vs comedic adventure movies', '2026-04-29T09:57:25.386601'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1433, 'Darker Tone & Genre Blend', '2026-03-04T04:56:55.992606'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1434, 'Romantic/comedic drama vs crime‑mystery', '2026-03-06T04:48:22.475835'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1435, 'Mature crime/drama TV series vs. family comedy', '2026-04-24T10:42:58.050225'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1436, 'Non-action comedy/documentary vs action-adventure', '2026-03-19T04:38:52.974296'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1437, 'Adult comedy‑drama movies vs short TV episodes', '2026-03-06T04:44:08.042348'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1438, 'Action/Adventure emphasis vs Crime/Drama focus', '2026-03-07T04:50:07.432529'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1439, 'Comedy Focus - Episodic Format', '2026-03-04T05:20:30.150077'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1440, 'Animated Family Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1441, 'Action-Focused Franchises', '2026-03-03T05:14:20.685809'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1442, 'Dark Comedy Crime Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1443, 'Live‑action drama focus', '2026-05-01T08:38:41.850691'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1444, 'Crime Films with Extended Runs', '2026-03-05T04:55:26.169397'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1445, 'Biography/Historical genre focus', '2026-03-23T10:42:20.360324'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1446, 'Based on true historical events', '2026-03-10T04:40:36.150720'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1447, 'Darker Tone & Genre Blend', '2026-03-04T05:09:56.740555'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1448, 'Short-Form Episodic Content', '2026-03-04T05:05:29.066763'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1449, 'Historical Biographical Dramas', '2026-03-03T04:45:51.099774'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1450, 'Comedy‑Crime/Drama blend versus straight drama', '2026-03-06T04:56:02.509189'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1451, 'Short-Form Comedy Series', '2026-03-03T04:53:43.490371'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1452, 'Fantasy‑comedy blend vs gritty realism', '2026-03-07T04:51:34.981461'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1453, 'Past/fantasy setting (non‑contemporary)', '2026-03-08T04:44:12.125459'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1454, 'TV drama/crime episodes vs feature‑length comedies', '2026-03-11T07:05:38.335374'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1455, 'Dystopian Sci-Fi with Mystery', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1456, 'Action/Comedy focus vs Drama/Mystery focus', '2026-04-27T10:51:43.005901'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1457, 'Animated Adventures vs. Dramatic Series', '2026-03-04T05:16:08.435906'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1458, 'Short comedic TV episodes', '2026-04-30T07:50:35.702814'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1459, 'Sci‑fi / mystery vs action‑adventure', '2026-03-09T04:43:33.623678'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1460, 'Comedy/romance TV episodes vs action‑crime movies', '2026-03-11T04:39:50.597017'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1461, 'Long action/adventure movies vs short sitcom episodes', '2026-03-07T14:19:51.581350'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1462, 'Crime Drama Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1463, 'Dark Crime Thrillers', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1464, 'Comedy‑tagged titles vs non‑comedy titles', '2026-04-29T17:21:36.975749'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1465, 'Action/Adventure titles with Comedy, Animation, or Horror', '2026-03-07T14:16:52.474035'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1466, 'Feature-length movies vs short TV episodes', '2026-03-08T04:42:21.719961'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1467, 'High-Concept Genre Blend', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1468, 'Science‑fiction tech focus vs non‑fiction/comedy', '2026-03-06T04:45:04.202230'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1469, 'Historical Drama Focus', '2026-03-04T05:03:19.246031'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1470, 'TV episode format over feature films', '2026-03-19T04:39:54.840962'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1471, 'Crime Dramas with Longer Runs', '2026-03-05T04:41:19.324521'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1472, 'Social conflict drama vs light romance/comedy', '2026-03-07T04:43:54.107492'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1473, 'Indie Family Dramas', '2026-03-04T04:56:28.871386'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1474, 'Western Crime Drama', '2026-03-04T05:02:52.490419'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1475, 'Action-Comedy vs. Character Drama', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1476, 'Intense drama series episodes vs light entertainment movies', '2026-03-06T04:50:08.062594'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1477, 'Science Fiction Action Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1478, 'Ensemble comedy‑drama with multiple protagonists', '2026-03-20T04:39:58.992207'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1479, 'Action‑focused titles', '2026-03-06T01:17:58.201113'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1480, 'Animated Family Content', '2026-03-03T05:00:07.875959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1481, 'Animated Family Adventure Films', '2026-03-05T04:57:10.488942'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1482, 'Features an actor named Aaron', '2026-03-07T08:28:47.369346'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1483, 'Action-Focused Military/Sci-Fi', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1484, 'Documentary Series Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1485, 'Action-Comedy Episodic Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1486, 'Adult-oriented serious genres vs Light comedy', '2026-03-09T04:42:59.631214'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1487, 'Crime‑drama TV episodes', '2026-03-10T04:41:00.755051'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1488, 'Animated Family Adventure Focus', '2026-03-05T05:17:07.959643'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1489, 'Speculative genre (sci‑fi/fantasy/superhero) focus', '2026-03-08T04:40:05.922890'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1490, 'Comedy‑focused short‑form episodes', '2026-03-10T04:42:49.142689'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1491, 'Comedy‑drama TV episodes vs sci‑fi/action drama', '2026-03-08T04:44:35.042402'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1492, 'Real-world documentary/travel and culinary focus', '2026-03-07T14:18:09.887735'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1493, 'Drama‑centric productions', '2026-03-06T01:16:22.665002'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1494, 'Comedy Focus / Episodic Structure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1495, 'Hour‑long serious drama episodes', '2026-04-27T01:35:23.729134'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1496, 'Stories about moving, homecoming, or time travel', '2026-03-09T04:43:14.529299'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1497, 'Action-Focused Episodic Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1498, 'Action-Focused, Fast-Paced Sequences', '2026-03-05T04:54:33.160162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1499, 'Titles feature a proper‑noun name', '2026-03-18T04:39:16.625817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1500, 'Stories set in non‑contemporary or exotic settings', '2026-03-06T04:40:52.379206'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1501, 'Dark Comedy Crime Series', '2026-03-04T05:07:43.973352'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1502, 'Family Restaurant Focus', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1503, 'Modern Streaming Series', '2026-03-05T04:43:08.292515'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1504, 'Short-Form Episodic Content', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1505, 'Absence of Comedy genre', '2026-04-27T01:22:18.621699'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1506, 'Procedural Medical Dramas', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1507, 'Character-Driven Dramas / Procedurals', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1508, 'Action Franchises with Long Runs', '2026-03-03T05:10:50.216974'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1509, 'Franchise Pattern: Established Worlds', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1510, 'Horror/Mystery Focus', '2026-03-05T05:01:48.647427'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1511, 'High-Budget Production Values', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1512, 'Romance/Fantasy genre presence', '2026-03-18T04:40:14.899947'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1513, 'WWII Historical Dramas', '2026-03-05T04:59:55.951162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1514, 'Short-Form Comedy Episodes', '2026-03-04T04:50:05.144913'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1515, 'Mainstream franchise episodes (non‑horror) vs horror/biopic', '2026-03-07T04:42:00.070275'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1516, 'Action‑genre titles', '2026-03-11T04:41:01.518378'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1517, 'Family-Focused Comedy & Adventure', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1518, 'Science Fiction Space Adventure', '2026-03-05T05:20:17.380194'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1519, 'Action-Documentary Hybrid', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1520, 'Contemporary crime‑drama focus', '2026-03-19T04:39:27.689742'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1521, 'High-Concept Mystery with Limited Scope', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1522, 'TV‑centric titles vs movie‑centric titles', '2026-04-27T01:13:55.886652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1523, 'Vacation retreat setting', '2026-04-27T10:50:07.662312'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1524, 'Dark Comedy Action', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1525, 'Primarily Comedy genre titles', '2026-03-06T04:49:22.179521'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1526, 'Comedy genre inclusion', '2026-03-07T04:45:47.312590'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1527, 'No‑Comedy titles', '2026-03-16T04:40:10.246028'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1528, 'Action‑Adventure vs Non‑Action Drama', '2026-03-06T04:47:18.932371'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1529, 'Thriller or Mystery genre presence', '2026-03-10T04:43:20.551043'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1530, 'Crime Family Power Dynamics', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1531, 'Action/Adventure‑driven titles', '2026-03-08T04:44:47.862695'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1532, 'Feature films vs TV episodes', '2026-03-07T14:26:07.021899'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1533, 'Short‑format sitcom/comedy TV episodes', '2026-04-30T07:50:50.146933'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1534, 'Action-Thriller with Distinct Formats', '2026-03-02T07:58:44.204046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1535, 'TV episode format vs feature film', '2026-03-06T04:52:03.808333'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                
COMMIT;
