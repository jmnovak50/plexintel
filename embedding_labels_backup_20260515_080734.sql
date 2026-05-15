-- Restore backup for embedding_labels
BEGIN;

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (0, 'Feature films vs TV episodes', '2026-05-03T11:16:24.296208'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1, 'Space‑opera franchise movies vs short comedy episodes', '2026-05-03T10:03:14.196072'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (2, 'Adventure feature films vs non‑adventure TV episodes', '2026-05-15T07:32:29.384111'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (3, 'Sequel or follow‑up titles', '2026-05-04T07:43:29.554045'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (4, 'Horror or Mystery genre presence', '2026-05-03T11:35:34.194115'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (5, 'Short comedic TV episodes vs longer dramatic films', '2026-05-03T13:40:17.757387'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (6, 'Drama‑focused TV episodes', '2026-05-03T10:18:30.760012'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (7, 'Light‑hearted, non‑franchise titles', '2026-05-03T10:53:49.768497'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (8, 'Action/Adventure vs Sitcom Comedy Episodes', '2026-05-03T13:15:21.582779'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (9, 'Crime genre presence', '2026-05-15T07:37:53.942509'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (10, 'Comedy/Family genre presence', '2026-05-03T12:21:33.563119'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (11, 'Action/Adventure genre focus', '2026-05-13T11:43:38.154520'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (12, 'Grounded realistic settings vs speculative/fantasy', '2026-05-03T13:04:00.898922'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (13, 'Non‑comedic adult drama/action episodes', '2026-05-03T12:03:25.945900'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (14, 'Short comedic action‑adventure TV episodes', '2026-05-12T07:58:22.534177'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (15, 'Comedy titles with music element', '2026-05-03T12:22:21.502294'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (16, 'Standard hour‑long drama/comedy TV episodes', '2026-05-12T07:43:59.086274'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (17, 'Contemporary crime‑drama vs period/fantasy', '2026-05-03T13:35:18.803472'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (19, 'Comedy vs non‑comedy', '2026-05-13T08:12:45.843401'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (20, 'Short episodic TV vs long feature films', '2026-05-14T09:04:51.866475'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (21, 'Comedy/Adventure tone vs Serious Drama tone', '2026-05-15T07:48:12.251046'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (23, 'Action‑Adventure franchise titles', '2026-05-12T07:55:16.904225'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (24, 'Comedy‑filled titles vs non‑comedic titles', '2026-05-13T11:42:26.318530'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (25, 'Comedy/Action‑Adventure vs Drama‑Mystery', '2026-05-12T07:42:20.153864'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (26, 'Fictional scripted entertainment vs nature documentary', '2026-05-03T11:02:08.515584'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (27, 'Road‑trip / travel‑centric stories', '2026-05-03T11:28:10.889630'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (28, 'Drama/Action/Mystery emphasis vs Comedy/Romance emphasis', '2026-05-05T07:57:58.743174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (29, 'Crime/Biography/History focus', '2026-05-03T12:05:05.375101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (30, 'Adult‑focused drama/comedy, excludes children/family', '2026-05-09T09:20:08.833142'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (31, 'Drama genre present', '2026-05-14T09:08:48.740686'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (32, 'Speculative fiction vs grounded reality', '2026-05-15T07:32:44.632245'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (33, 'Serious non‑comedy genre vs comedy', '2026-05-03T11:58:01.558245'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (34, 'Science‑fiction / speculative setting', '2026-05-03T12:07:32.217388'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (35, 'Standalone dramatic episodes (no major franchise)', '2026-05-09T09:16:01.610424'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (36, 'Non‑fiction (docu/biography) titles vs pure drama episodes', '2026-05-15T07:49:00.472508'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (37, 'Action/Fantasy vs Drama/Biopic', '2026-05-03T11:31:08.401744'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (38, 'Comedy‑laden TV episodes vs serious feature films', '2026-05-14T08:21:01.251015'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (39, 'Speculative or historical setting', '2026-05-03T12:21:53.535963'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (40, 'Prestige drama and documentary titles vs sitcom comedy', '2026-05-15T07:49:30.390253'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (41, 'Episodes featuring a cast member named Adam', '2026-05-03T13:29:21.435602'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (42, 'Adventure/Action comedy vs crime/drama', '2026-05-15T07:43:59.301528'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (43, 'Horror‑Mystery genre blend', '2026-05-15T07:42:42.183530'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (44, 'Obscure niche series vs mainstream franchises', '2026-05-03T13:13:32.261640'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (45, '60‑minute episodic, non‑adult titles vs shorter/edgier', '2026-05-03T11:09:04.134348'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (47, 'Feature-length movies vs TV episodes', '2026-05-06T07:51:54.842622'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (48, 'Series episodes vs standalone movies', '2026-05-11T08:03:14.475983'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (49, 'Light comedy or nature documentary episodes', '2026-05-03T12:48:13.146192'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (50, 'Comedy‑centric titles vs non‑comedy titles', '2026-05-12T08:09:21.676125'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (52, 'Adult superhero/comic action vs teen comedy', '2026-05-03T11:24:47.957501'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (53, 'Non‑biographical titles', '2026-05-14T08:26:32.692600'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (54, 'Contains cast member named Adam', '2026-05-07T07:54:53.887073'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (55, 'Comedy‑Drama emphasis versus Action‑Heavy titles', '2026-05-03T12:39:21.983337'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (56, 'Longer, non‑comedy episodes/movies vs short comedies', '2026-05-15T07:33:48.571359'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (57, 'TV episode vs feature film', '2026-05-03T12:08:00.807864'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (58, 'Real-life biography/documentary focus', '2026-05-14T09:22:02.005308'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (60, 'Historical period settings vs modern/fantasy settings', '2026-05-03T10:45:28.345535'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (61, 'Sci‑fi/Action franchise content vs Light‑tone genre', '2026-05-03T13:05:41.299759'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (62, 'Includes History genre', '2026-05-03T12:49:26.594279'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (63, 'Comedy‑driven light genre blends', '2026-05-03T11:22:42.149771'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (65, 'Institutional Power Struggles vs Personal Slice‑of‑Life', '2026-05-14T09:21:26.433700'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (66, 'TV episodes vs feature films', '2026-05-03T12:25:15.238129'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (67, 'Comedy presence vs serious tone', '2026-05-03T13:38:35.860151'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (68, 'Grounded real‑world stories', '2026-05-03T13:26:42.312297'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (69, 'Prestige adult drama vs family/teen fare', '2026-05-14T09:13:55.984565'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (70, 'Historical crime/drama set in 1950s‑60s', '2026-05-03T12:03:39.554027'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (71, 'Alternate or speculative setting', '2026-05-15T07:35:43.257079'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (72, 'Adult scripted action/fantasy vs family/real-life', '2026-05-03T10:30:29.601668'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (73, 'Comedy/Action/Film titles vs straight drama episodes', '2026-05-03T09:39:14.615828'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (74, 'Biopic films vs non‑biopic TV episodes', '2026-05-03T12:04:06.072110'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (75, 'Futuristic Action‑Adventure vs. Light Comedy', '2026-05-15T07:36:36.078133'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (76, 'Feature films vs TV episodes', '2026-05-10T08:11:24.482546'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (77, 'Drama-focused vs Comedy-focused', '2026-05-09T09:16:50.993187'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (79, 'Crime‑focused narratives', '2026-05-13T11:44:10.847940'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (81, 'Serious live-action crime/drama (no comedy/animation)', '2026-05-03T10:47:50.975891'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (82, 'Modern adult live-action vs. historical/animated', '2026-05-03T11:00:16.956195'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (84, 'Documentary/Nature episodes vs scripted comedy shows', '2026-05-15T07:35:55.588412'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (85, 'Franchise sci‑fi episodes vs non‑franchise titles', '2026-05-05T08:00:12.939973'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (86, 'Non‑comedic action/drama titles vs comedy/documentary', '2026-05-03T10:28:02.616256'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (87, 'Presence of Comedy genre', '2026-05-03T13:22:40.577476'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (88, 'High critic rating (8+ IMDb) vs low rating', '2026-05-13T11:26:13.544422'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (89, 'Contemporary comedy‑drama with romance', '2026-05-03T10:37:01.141688'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (90, 'TV episode vs film/miniseries', '2026-05-03T10:34:00.504791'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (91, 'Romance genre presence', '2026-05-12T07:37:24.659914'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (92, 'Standard-length TV episodes vs mixed formats', '2026-05-03T10:46:06.610104'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (93, 'Short-form TV episodes vs feature-length movies', '2026-05-13T08:12:05.305091'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (94, 'TV episode format (sub‑hour) vs feature film', '2026-05-15T07:45:02.592433'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (95, 'Crime-focused narratives', '2026-05-03T10:07:38.271414'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (96, '2020s TV episodes', '2026-05-05T08:56:24.518462'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (97, 'Comedy‑centric titles vs serious drama', '2026-05-15T07:52:43.451666'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (98, 'Series repetition vs isolated episodes', '2026-05-15T07:45:26.686641'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (99, 'Fiction vs Documentary', '2026-05-08T07:45:50.352285'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (100, 'Music‑centric content vs crime‑drama content', '2026-05-15T07:41:55.365783'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (101, 'Subtitle‑titled episodes vs plain series titles', '2026-05-03T08:45:07.429928'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (102, 'Comedy‑focused titles', '2026-05-13T08:04:10.480352'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (103, 'Sports and physical competition focus', '2026-05-15T07:37:19.405103'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (104, 'Action/Adventure emphasis vs Drama/Western emphasis', '2026-05-07T07:47:53.787002'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (106, 'Dark adult drama with violent or historical themes', '2026-05-13T07:55:36.403109'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (107, 'All principal cast first names start with A', '2026-05-03T12:47:36.091272'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (108, 'Romance or period‑setting genres (Romance, History, Western)', '2026-05-03T11:46:04.209435'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (110, 'Fantasy / Supernatural Elements', '2026-05-03T11:18:32.837644'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (112, 'Low‑violence, non‑action content', '2026-05-06T07:43:56.573537'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (113, 'Family-friendly fantasy/adventure vs adult crime drama', '2026-05-15T07:34:04.648250'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (114, 'Speculative/Thriller settings vs realistic drama', '2026-05-15T07:56:09.097749'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (116, 'Adult‑oriented comedy‑drama with crime/biography', '2026-05-14T09:21:42.590524'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (117, 'Recent drama‑focused TV episodes', '2026-05-03T12:06:26.111998'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (118, 'Episode-length TV shows vs feature-length movies', '2026-05-14T09:10:34.095817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (119, 'Period/Fantasy setting vs modern contemporary setting', '2026-05-15T07:46:10.472148'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (121, 'Light comedy‑drama tone vs action‑heavy content', '2026-05-03T10:22:52.915857'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (123, 'Adult live-action drama vs family/animation', '2026-05-07T07:45:00.356116'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (124, 'Short comedic TV episodes vs long dark movies', '2026-05-04T07:55:23.855551'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (126, 'Comedy‑genre titles', '2026-05-13T08:14:40.427773'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (128, 'Animation, sci‑fi or musical emphasis', '2026-05-03T12:11:36.725419'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (129, 'Family-friendly comedy', '2026-05-03T13:36:50.149557'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (130, 'Long-form drama vs short sitcom episodes', '2026-05-14T08:23:11.215586'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (132, 'Low-rated titles vs high-rated titles', '2026-05-03T10:33:23.059171'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (133, 'Contemporary relationship‑centric comedy/drama', '2026-05-03T12:42:25.087643'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (134, 'Single‑episode releases', '2026-05-03T10:50:41.374967'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (136, 'Science‑fiction or mystery drama focus', '2026-05-15T07:50:12.163649'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (137, 'Presence of Mystery genre', '2026-05-11T08:06:38.490833'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (138, 'Major franchise / high‑profile creator affiliation', '2026-05-03T10:09:45.442867'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (139, 'Short TV episodes (under 45 minutes)', '2026-05-13T07:55:52.905460'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (140, 'Feature-length movies vs short TV episodes', '2026-05-15T07:40:14.742966'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (141, 'Romance genre presence', '2026-05-05T08:47:51.932231'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (142, 'Established scripted TV series episodes', '2026-05-03T11:26:47.000003'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (143, 'Horror and thriller titles', '2026-05-11T21:22:53.953368'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (145, 'Feature-length movies vs short TV episodes', '2026-05-03T12:14:00.093642'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (146, 'Crime/Mystery/Thriller genre focus', '2026-05-14T09:07:39.513721'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (147, 'Based on real events or people', '2026-05-15T07:52:30.677123'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (148, 'Standalone films/series vs single-episode TV entries', '2026-05-15T07:57:07.444562'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (149, 'Food‑themed episode titles', '2026-05-09T09:18:29.692687'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (150, 'Short-form scripted adventure/quest narratives', '2026-05-03T13:24:43.188803'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (151, 'TV episodes vs theatrical movies', '2026-05-03T10:10:45.493658'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (152, 'Action/Adventure/Western focus, no romance', '2026-05-03T11:12:16.403691'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (153, 'Grounded dramedy vs genre‑heavy shorts', '2026-05-03T11:26:21.799266'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (154, 'Star Trek franchise titles', '2026-05-03T12:35:05.035842'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (155, 'Franchise/event tie-in episodes', '2026-05-03T11:15:43.127171'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (156, 'TV episode vs feature film', '2026-05-03T12:45:38.036953'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (157, 'Focus on historical or real-world figures/events', '2026-05-14T08:15:22.176571'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (158, 'Comedy‑drama TV episodes (30‑55 min)', '2026-05-14T09:12:32.757391'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (159, 'Drama/Action focus vs Comedy/Family focus', '2026-05-15T07:42:28.865239'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (160, 'Intense thriller/action genres vs light comedy/romance', '2026-05-10T08:06:47.055955'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (161, 'Party-focused episodes and films', '2026-05-03T13:12:12.578396'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (162, 'Early series installments (pilots/first seasons)', '2026-05-15T07:37:40.060734'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (163, 'Action‑oriented genre blends with sci‑fi/fantasy', '2026-05-03T12:59:22.651824'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (164, 'Comedy‑tagged titles vs non‑comedy titles', '2026-05-11T21:25:16.701367'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (165, 'Serious high‑stakes drama vs light‑hearted comedy', '2026-05-15T07:47:13.850603'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (166, 'Feature-length or documentary format', '2026-05-03T13:00:43.478871'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (167, 'Short dramatic action/crime TV episodes', '2026-05-14T08:27:44.285249'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (168, 'Serious adult drama/thriller vs light romance/fantasy', '2026-05-03T13:32:37.385381'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (169, 'Features Crime, Horror, or Sci‑Fi genres', '2026-05-03T10:35:08.365021'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (170, 'Mythic/fantasy literary adaptations', '2026-05-12T07:48:09.266261'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (171, 'Series‑level vs Episode‑level', '2026-05-12T08:02:08.236731'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (172, 'Centered on individual protagonist', '2026-05-10T08:12:16.696130'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (173, 'Adventure genre emphasis', '2026-05-15T07:40:31.965637'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (174, 'Emphasis on friendship/romantic relationship themes', '2026-05-13T11:38:50.474428'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (175, 'Grounded drama/scifi vs supernatural/fantasy comedy', '2026-05-11T07:48:44.638127'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (176, 'Comedy vs Serious drama', '2026-05-09T09:13:36.486584'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (177, 'TV episodes and series entries', '2026-05-14T08:25:08.744154'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (178, 'Action‑heavy short‑form TV episodes', '2026-05-03T12:20:05.110204'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (179, 'Live-action adventure‑drama focus', '2026-05-14T08:59:49.606911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (180, 'TV episodes vs feature films', '2026-05-14T09:15:53.866245'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (181, 'Short-form drama episodes vs feature-length movies', '2026-05-09T07:41:27.742853'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (182, 'Includes Comedy genre', '2026-05-10T08:20:21.651632'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (183, 'Comedy sitcom episodes vs serious drama', '2026-05-03T12:26:45.750848'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (184, 'Short‑form episodic content vs feature‑length movies', '2026-05-03T11:18:01.852478'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (187, 'Pre‑2015 releases', '2026-05-03T11:47:20.664558'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (188, 'Adventure genre presence', '2026-05-03T11:25:26.540924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (190, 'Action‑focused titles', '2026-05-03T11:06:35.051279'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (191, 'Comedy‑focused sitcoms vs action‑drama episodes', '2026-05-10T08:02:24.929736'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (192, 'Comedy sitcom episodes vs Action‑drama movies', '2026-05-03T11:18:14.976574'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (193, 'Action‑heavy, serious‑tone titles', '2026-05-03T10:38:22.973585'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (197, 'Real‑world/historical setting vs speculative/futuristic', '2026-05-09T07:44:16.020993'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (198, 'Lead cast member named Alex/Aaron', '2026-05-03T11:16:39.484398'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (199, 'Episode-focused titles vs feature-length films', '2026-05-03T12:07:49.058523'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (200, 'Feature-length movies (≈100+ min)', '2026-05-03T10:26:56.019586'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (201, 'Sci‑fi franchise episodes vs grounded contemporary drama', '2026-05-08T08:03:18.288342'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (202, 'Adventure‑Fantasy/Action focus', '2026-05-13T07:52:33.829719'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (203, 'Supernatural or fantasy horror elements', '2026-05-03T10:20:51.790060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (204, 'Drama without Horror/Action', '2026-05-03T12:36:06.490670'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (205, 'Exotic or remote location setting', '2026-05-03T12:49:07.103543'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (206, 'Feature-length movies vs short TV episodes', '2026-05-14T08:03:04.304456'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (207, 'Fantasy/Adventure speculative focus', '2026-05-11T07:57:24.513488'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (208, 'Gritty crime/action drama vs light comedy/romance', '2026-05-04T08:02:58.286998'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (209, 'Feature-length movies vs TV episodes', '2026-05-11T21:25:49.653257'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (210, 'Crime/Biography‑Driven Drama', '2026-05-04T07:50:07.178079'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (211, 'Comedy genre vs Drama/Mystery tone', '2026-05-03T12:32:00.594305'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (213, 'Violent or aggressive episode titles', '2026-05-15T07:55:26.145165'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (214, 'Adult‑focused titles vs child/teen programming', '2026-05-12T07:40:53.161471'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (215, 'Comedy vs Drama', '2026-05-15T07:57:34.395121'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (216, 'Real-world drama vs. comedic/fantasy series', '2026-05-06T07:53:13.650040'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (217, 'Pregnant female lead in historical/dramatic narratives', '2026-05-03T13:07:30.222992'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (218, 'Episode-length TV series entries vs feature films', '2026-05-03T12:45:55.499059'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (219, 'Period/Historical setting', '2026-05-03T12:08:42.855859'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (220, 'Drama TV episodes vs Comedy sitcom episodes', '2026-05-15T07:39:44.074118'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (222, 'No crime genre', '2026-05-15T07:33:34.349262'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (223, 'Comedy genre presence', '2026-05-03T10:59:34.270817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (224, 'Predominantly Comedy titles', '2026-05-03T11:21:12.557408'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (225, 'Feature-length movies vs TV episodes', '2026-05-15T07:47:00.484823'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (226, 'Drama genre present', '2026-05-03T11:20:51.929496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (227, 'Feature films vs short TV/comedy episodes', '2026-05-03T12:09:12.680207'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (228, 'Action/Sci‑Fi titles vs Comedy/Animation', '2026-05-04T07:54:37.309459'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (229, 'Serious live-action drama vs animated/comedy', '2026-05-13T08:08:49.147795'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (230, 'Short comedic TV episodes/seasons', '2026-05-03T12:57:17.066291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (231, 'Parent‑child relationship focus', '2026-05-07T07:48:23.613528'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (232, 'Original/comedy‑drama titles vs franchise sci‑fi', '2026-05-03T12:35:36.209392'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (233, 'Long-form action/adventure movies vs short comedy episodes', '2026-05-03T13:27:27.230282'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (234, 'Action‑Adventure genre blend vs straight drama', '2026-05-14T08:09:07.427053'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (235, 'Feature-length or multi-episode titles', '2026-05-03T11:56:54.728104'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (236, 'Non‑crime titles vs crime titles', '2026-05-03T09:55:45.413732'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (238, 'Action‑Adventure focus', '2026-05-10T08:08:50.374445'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (240, 'Action‑Crime TV episodes vs other formats', '2026-05-05T07:55:56.705031'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (242, 'Action/Adventure focus', '2026-05-06T07:55:55.875963'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (243, 'Serial drama episodes vs films/comedic episodes', '2026-05-15T07:51:42.935934'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (244, 'Short-form TV episodes vs feature-length movies', '2026-05-15T07:31:31.079695'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (245, 'Non‑comedy serious titles', '2026-05-14T09:07:58.573894'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (246, 'Short TV episodes vs feature-length movies', '2026-05-03T11:04:44.350828'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (247, 'Action/Crime/Adventure titles vs. Comedy/Drama titles', '2026-05-03T11:34:08.864450'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (248, 'Action/Adventure & Documentary vs. Comedy/Romance', '2026-05-05T08:01:42.736333'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (249, 'Fantastical settings vs grounded drama', '2026-05-13T11:36:55.056573'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (250, 'Comedy‑centric titles', '2026-05-14T09:06:42.119173'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (252, 'Action‑Adventure/comedy mix vs non‑action dramas', '2026-05-03T13:04:15.603568'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (253, 'Action/Adventure focus vs crime‑drama focus', '2026-05-03T09:38:46.706352'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (254, 'Sci‑Fi/Action vs Half‑Hour Sitcom', '2026-05-14T08:16:47.223428'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (255, 'Comedy/Action‑heavy titles vs serious drama/crime', '2026-05-14T09:20:49.413174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (256, 'Family‑oriented animated/comedy titles', '2026-05-11T08:04:50.200238'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (257, 'Comedy blended with drama/action/real‑world genres', '2026-05-03T12:44:32.888788'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (258, 'Feature films versus TV episode titles', '2026-05-03T13:40:31.833174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (259, 'High‑octane action franchise or series episodes', '2026-05-03T12:48:29.708034'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (260, 'Episode-focused titles vs feature films', '2026-05-14T09:24:50.634429'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (261, 'Includes feature‑film titles', '2026-05-05T08:36:22.863294'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (263, 'Political/Historical drama vs comedy‑crime', '2026-05-03T12:09:46.850416'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (264, 'Serious drama tone vs comedic tone', '2026-05-03T10:24:17.781879'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (267, 'Historical/real-world focus vs speculative/futuristic', '2026-05-15T07:51:11.226144'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (268, 'Adult‑oriented live‑action titles', '2026-05-03T08:02:03.249350'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (269, 'No explicit sci‑fi/fantasy/horror genre', '2026-05-13T08:09:53.501545'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (270, 'Short comedic TV episodes vs long serious productions', '2026-05-15T07:49:41.896427'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (271, 'Live-action narrative fiction vs documentary/animation', '2026-05-03T11:54:50.760444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (272, 'Future/dystopian settings vs contemporary/historical', '2026-05-03T12:20:51.371289'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (273, 'Crime‑oriented action/comedy blends', '2026-05-15T07:42:12.891180'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (274, 'Pure comedy or single‑genre focus', '2026-05-03T12:35:52.413381'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (275, 'Lighthearted tone vs gritty crime/horror', '2026-05-03T12:54:41.724112'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (276, 'Crime‑focused investigative drama', '2026-05-03T12:50:34.534559'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (277, 'Grounded drama/biography vs sci‑fi/fantasy', '2026-05-03T12:18:34.913817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (278, 'TV episode format vs theatrical movie', '2026-05-03T13:04:54.382067'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (279, 'Crime genre presence', '2026-05-03T13:09:10.975572'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (280, 'Speculative sci‑fi and documentary focus', '2026-05-15T07:50:54.751222'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (281, 'Short‑form TV episodes (under 45 min)', '2026-05-03T11:03:31.674956'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (282, 'Standalone themed short TV episodes', '2026-05-03T11:33:19.747249'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (283, 'Single-episode short-form content', '2026-05-03T12:37:56.209666'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (284, 'Standalone drama series episodes', '2026-05-03T13:06:00.832101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (285, 'Short, comedic or animated TV episodes', '2026-05-13T08:17:56.182061'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (286, 'Longer runtime (≈1 hour+)', '2026-05-14T09:23:32.170057'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (287, 'Light‑hearted comedy/romance and reality formats', '2026-05-03T11:21:40.814114'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (288, 'Action‑driven genre titles vs drama‑centric episodes', '2026-05-03T10:45:10.286665'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (289, 'Grounded contemporary drama (no fantasy/superhero elements)', '2026-05-15T07:53:38.129761'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (290, 'Short drama TV episodes vs feature films', '2026-05-14T08:24:27.167873'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (291, 'Comedy genre presence', '2026-05-03T11:22:26.659250'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (292, '2020s contemporary releases', '2026-05-03T08:38:12.993725'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (293, 'Primary genre other than crime', '2026-05-03T12:38:45.464771'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (294, 'Family‑oriented animation/comedy vs adult crime/drama', '2026-05-14T09:25:20.367536'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (295, 'Crime/Action drama focus vs light comedy romance', '2026-05-15T07:46:36.935755'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (296, 'Comedy/Drama TV episodes vs Sci‑Fi/Action titles', '2026-05-03T11:29:55.586103'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (297, 'Action‑genre titles', '2026-05-14T09:10:20.640228'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (298, 'Television episodes/season vs theatrical movies', '2026-05-03T12:33:34.883981'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (299, 'Presence of Crime genre', '2026-05-03T11:29:36.339722'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (300, 'Futuristic / sci‑fi / tech‑centric content', '2026-05-13T11:37:50.201151'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (301, 'Intimate character‑driven drama', '2026-05-03T13:18:06.636700'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (303, 'High: Action/Adventure or Crime; Low: Comedy/Reality', '2026-05-09T09:00:30.829885'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (304, 'Newer series episodes vs established franchise/film', '2026-05-15T07:43:13.746494'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (305, 'Includes sci‑fi or biography genre', '2026-05-03T12:34:53.810711'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (306, 'Standalone TV episodes vs movies/season collections', '2026-05-03T12:38:57.826961'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (308, 'Grounded live-action drama (no fantasy or animation)', '2026-05-07T07:41:24.511497'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (310, 'Lighthearted family/animation titles vs gritty action/drama', '2026-05-05T08:02:02.477333'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (311, 'Includes Drama genre', '2026-05-03T10:37:55.696138'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (313, 'Comedy‑genre titles', '2026-05-03T13:01:21.012370'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (314, 'Action‑Adventure vs Crime/Drama', '2026-05-05T08:47:34.252020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (315, 'Includes Comedy genre', '2026-05-14T09:25:57.692045'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (316, 'Feature films vs TV episodes', '2026-05-12T08:04:27.071554'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (317, 'Historical war/period dramas', '2026-05-03T12:37:17.066802'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (318, 'Episodic speculative TV series vs standalone films', '2026-05-03T13:42:48.361677'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (319, 'Real-life drama vs action‑driven spectacle', '2026-05-03T10:11:34.614668'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (320, 'Comedy‑tagged TV episodes', '2026-05-03T09:51:32.972918'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (322, 'Non‑fantasy (HIGH) vs fantasy (LOW) titles', '2026-05-05T08:40:54.855480'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (323, 'Crime‑drama focused TV episodes', '2026-05-13T08:17:33.149323'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (324, 'Television episode format', '2026-05-03T12:31:38.136997'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (325, 'Youth‑oriented TV episodes vs adult drama/action', '2026-05-14T08:06:30.273500'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (326, 'Includes Comedy genre', '2026-05-03T12:22:57.530585'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (328, 'Single‑episode serious genre vs multi‑episode/comedy formats', '2026-05-12T07:54:34.930308'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (329, 'Titles featuring a cast member named Adam', '2026-05-03T08:35:32.414970'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (330, 'Drama with non‑comedic genre blend', '2026-05-03T13:11:15.839818'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (331, 'Television series/episodes (non‑film)', '2026-05-04T07:53:57.780268'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (332, '≈50‑minute drama TV episodes', '2026-05-15T07:54:17.152366'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (333, 'Speculative/fantasy settings vs grounded realism', '2026-05-06T07:56:50.477814'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (334, 'Crime genre absent vs present', '2026-05-03T11:27:55.734010'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (335, 'Long‑form drama vs short sitcom comedy', '2026-05-03T10:40:40.444996'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (336, 'Science-fiction and franchise-driven action titles', '2026-05-03T12:13:30.868569'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (338, 'Lighthearted comedy/family tone vs dark horror', '2026-05-03T11:05:15.559499'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (339, 'Sequel or ongoing series entries', '2026-05-03T11:15:28.574973'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (340, 'Serious drama & documentary tone', '2026-05-12T07:52:18.397264'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (341, 'Short-form, low-rated or unrated TV episodes', '2026-05-12T08:09:02.139182'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (342, 'Real-world contemporary drama (law, biography, fashion)', '2026-05-14T09:24:35.052336'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (343, 'Comedy‑tagged episodes vs non‑comedy titles', '2026-05-03T10:53:32.109693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (344, 'Feature film presence vs episode‑only', '2026-05-03T12:29:34.580212'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (345, 'TV episode/season format vs feature film', '2026-05-11T21:20:36.902092'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (346, 'Cast member with first name starting “Ab”', '2026-05-04T07:47:06.338850'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (347, 'Comedy‑focused short TV episodes', '2026-05-03T13:19:50.850714'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (348, 'Action/Adventure/Comedy vs Drama/Mystery', '2026-05-04T07:40:19.450440'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (349, 'Comedy/Action‑Adventure titles vs Solely Drama/Mystery', '2026-05-12T07:36:38.937710'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (350, 'Longer, dramatic episodes vs short sitcom seasons', '2026-05-05T08:46:15.225561'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (351, 'Mature action/comedy content vs family/serious drama', '2026-05-03T09:47:48.686924'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (352, 'Standalone anthology/educational episodes vs serialized plot episodes', '2026-05-12T07:45:07.061393'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (353, 'Features cast member named Adam', '2026-05-03T12:43:06.647782'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (354, 'Drama series episodes vs non‑episode films', '2026-05-03T11:33:01.937797'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (355, 'Non‑Action genres vs Action/Adventure/Thriller', '2026-05-03T12:45:00.911800'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (356, 'Sub‑hour episode length', '2026-05-14T09:05:42.882077'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (357, 'Fictional scripted episodes vs documentary/sport/animation', '2026-05-03T11:43:34.087550'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (358, 'Primary drama focus', '2026-05-03T10:33:39.672467'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (359, 'Comedy-focused titles vs Action/Adventure/Horror', '2026-05-03T10:11:59.580820'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (360, 'Mid-length drama TV episodes', '2026-05-09T09:18:50.489210'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (361, 'Feature-length movies vs episode-only', '2026-05-03T07:57:25.362110'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (362, 'Drama genre present', '2026-05-03T11:12:55.191752'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (363, 'Comedy/Action‑heavy vs Drama‑focused', '2026-05-03T10:21:50.847476'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (364, 'Comedy/romance genre vs horror genre', '2026-05-03T12:37:41.743395'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (365, 'Focus on crime or mystery investigations', '2026-05-03T11:11:48.657513'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (366, 'Comedy genre presence', '2026-05-03T10:49:33.368474'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (368, 'Short TV episodes vs feature-length movies', '2026-05-03T09:59:36.876406'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (369, 'Comedy-driven short-form TV episodes', '2026-05-03T11:47:03.010864'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (370, '30‑minute network sitcom episodes', '2026-05-14T08:07:53.337852'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (372, 'Light‑hearted TV episodes vs gritty blockbuster films', '2026-05-13T08:13:08.336621'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (373, 'Original standalone works vs franchise tie‑ins', '2026-05-12T07:39:01.461465'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (374, 'Includes a cast member named Adam', '2026-05-03T09:54:24.518351'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (375, 'Aaron in cast', '2026-05-09T09:17:06.527335'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (376, 'Action/Crime/Sci‑Fi vs Light comedy‑drama', '2026-05-03T12:10:40.077015'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (377, 'Comedy‑heavy or genre‑blended titles vs serious drama', '2026-05-13T08:01:34.963680'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (378, 'Female lead vs male lead', '2026-05-15T07:51:30.049415'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (380, 'Crime genre presence', '2026-05-04T07:42:01.981044'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (381, 'Includes Action or Comedy genre', '2026-05-03T11:25:49.940356'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (382, 'Live-action vs animated titles', '2026-05-07T07:46:49.092096'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (383, 'Recent dark-action thriller titles vs older family comedies', '2026-05-13T11:32:03.244156'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (384, 'Fictional scripted drama/action vs nonfiction documentary/comedy', '2026-05-03T11:10:24.357950'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (385, 'Starts with letter S', '2026-05-03T12:30:42.379336'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (388, 'Low critical rating versus high critical rating', '2026-05-15T07:47:35.446886'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (389, 'TV episodes vs theatrical movies', '2026-05-03T13:07:43.031838'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (390, 'Drama‑centric TV episodes without sci‑fi', '2026-05-03T11:17:34.961649'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (391, 'Presence of Action genre', '2026-05-03T07:34:15.043390'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (392, 'Adventure treasure‑hunt focus', '2026-05-11T07:50:43.532110'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (393, 'Predominantly drama‑genre titles', '2026-05-14T08:03:28.138226'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (394, 'Youth‑oriented / family‑friendly content', '2026-05-03T12:15:14.328915'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (395, 'Includes Drama genre', '2026-05-03T12:27:50.773444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (396, 'Comedy‑centric short episodes vs. horror mini‑series', '2026-05-03T10:15:07.497114'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (397, 'Legal/justice‑centered protagonists', '2026-05-14T09:09:06.205931'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (398, 'Drama‑centric serious genres vs light/comedic or horror', '2026-05-03T12:55:58.748606'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (399, '45‑60 min serialized drama episodes', '2026-05-03T10:30:54.657268'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (400, 'Star‑driven scripted narratives vs unscripted reality shows', '2026-05-03T12:08:16.313718'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (401, 'Franchise blockbusters vs niche/standalone titles', '2026-05-03T10:50:20.383152'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (402, 'Adult drama/action vs family‑oriented fare', '2026-05-05T09:02:39.654553'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (404, 'One‑hour episode length', '2026-05-13T08:18:34.221947'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (405, 'Longer episode runtimes (≈50‑60 min)', '2026-05-11T07:49:45.178237'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (406, 'Original/standalone titles vs franchise or sequel titles', '2026-05-03T11:20:15.733991'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (407, 'Adventure‑drama TV episodes', '2026-05-03T13:27:54.998116'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (408, 'Series episodes vs feature films', '2026-05-14T09:26:17.790785'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (409, 'Long, high‑rated drama/adventure vs short comedy TV episodes', '2026-05-03T12:51:50.569469'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (410, 'Action‑Adventure focus', '2026-05-03T13:21:10.111598'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (411, 'Franchise action‑adventure sci‑fi/fantasy', '2026-05-15T07:34:43.435814'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (412, 'Contains non‑drama genre (Adventure, Animation, Travel)', '2026-05-09T09:05:52.318658'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (413, 'Includes Action genre', '2026-05-15T07:39:24.222615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (414, 'Crime, Comedy, or Documentary genre focus', '2026-05-03T08:47:57.020087'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (415, 'Includes comedy genre', '2026-05-11T21:19:08.702052'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (416, 'Serious drama/mystery (often sci‑fi) vs comedy/fantasy', '2026-05-03T10:05:34.992271'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (417, 'Speculative or thriller genres vs pure comedy', '2026-05-10T08:08:36.317605'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (418, 'TV episodes vs feature films', '2026-05-03T11:31:58.221902'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (419, 'Star Trek sci‑fi titles vs non‑sci‑fi dramas', '2026-05-03T10:51:23.794309'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (420, 'First‑season or pilot episodes', '2026-05-09T07:53:07.340255'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (421, 'Episode length TV shows vs feature films', '2026-05-10T08:18:00.167303'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (422, 'Episode length TV shows vs feature-length movies', '2026-05-04T07:45:44.215702'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (423, 'Comedy‑Drama episodes vs non‑comedy longer formats', '2026-05-03T12:26:18.903933'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (425, 'Everyday occupation focus vs war/conflict narratives', '2026-05-13T11:45:00.011685'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (426, 'Action‑Adventure vs Non‑Action', '2026-05-03T10:52:56.985550'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (427, 'Earthbound, non‑speculative settings', '2026-05-03T10:59:48.234080'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (428, 'Comedy‑Drama genre blend', '2026-05-03T12:02:06.667360'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (429, 'Standard hour‑long live‑action drama episodes', '2026-05-12T07:55:37.960545'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (430, 'Includes Action or Fantasy genre', '2026-05-03T10:39:16.272025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (431, 'Character-focused TV episodes over action‑heavy films', '2026-05-03T11:52:23.808142'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (432, 'Family‑oriented titles vs non‑family titles', '2026-05-03T12:55:22.412652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (433, 'Standalone episodes with distinct casts', '2026-05-03T11:51:21.264098'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (434, 'Feature films vs short TV episodes', '2026-05-03T13:28:41.566280'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (435, 'Action/Adventure or Fantasy genre blend', '2026-05-03T12:16:44.126953'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (436, 'Contemporary pop‑culture focus', '2026-05-03T12:45:18.553570'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (437, 'Human‑focused live‑action episodes vs non‑human/fantasy', '2026-05-15T07:41:05.887291'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (438, 'Real‑world drama/comedy TV episodes', '2026-05-03T11:22:12.984174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (439, 'Kids sitcom episodes vs adult long‑form titles', '2026-05-03T10:43:04.063625'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (440, 'Action-heavy titles vs non-action titles', '2026-05-14T09:21:06.465562'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (441, 'Single-installment titles vs multi-episode seasons', '2026-05-03T12:39:39.819011'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (442, 'Lighthearted genre‑blend entertainment vs serious biopic drama', '2026-05-14T09:09:41.458002'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (444, 'Crime‑centric contemporary TV episodes', '2026-05-03T10:17:43.189483'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (445, 'Action‑Adventure genre emphasis', '2026-05-08T07:49:01.501319'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (446, 'Includes Crime genre', '2026-05-14T08:07:01.459316'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (447, 'Drama‑inclined titles vs pure comedy episodes', '2026-05-03T12:52:09.785801'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (448, 'Short TV episodes vs feature-length movies', '2026-05-03T12:53:37.593876'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (449, 'Comedy genre present', '2026-05-09T07:55:51.513935'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (450, 'Primary genre outside Action/Crime', '2026-05-12T08:05:50.580517'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (451, 'Contemporary or recent‑past settings', '2026-05-13T11:32:54.712622'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (453, 'Episode format (TV) versus feature-length movies', '2026-05-03T10:38:46.957867'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (454, 'Scripted live-action TV episodes', '2026-05-03T11:46:44.503502'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (456, 'TV episodes vs feature films', '2026-05-15T07:33:20.718828'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (457, 'Lighthearted comedy‑drama vs serious drama', '2026-05-13T11:24:44.311677'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (458, 'Low-rated titles vs high-rated titles', '2026-05-07T07:57:51.241174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (459, 'Comedic or upbeat tone vs serious drama', '2026-05-13T07:58:08.854650'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (460, 'Feature films vs TV episodes', '2026-05-03T11:05:01.999688'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (461, 'Feature films and one‑off episodes vs series episodes', '2026-05-03T12:14:44.463536'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (462, 'Episode‑centric releases vs feature films', '2026-05-03T13:04:38.048359'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (463, 'Non‑fiction (documentary/biography) content', '2026-05-03T12:25:00.377939'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (464, 'Standalone episodes/films versus multi‑episode seasons', '2026-05-03T09:57:22.239603'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (465, 'Contemporary real‑world setting', '2026-05-03T11:59:04.846159'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (467, 'Adult‑oriented hour‑long dramatic TV episodes', '2026-05-03T12:12:02.877608'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (468, 'TV series episodes and seasons', '2026-05-14T09:13:37.855617'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (469, 'Comedy genre presence', '2026-05-13T08:15:22.179854'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (470, 'Action‑Adventure blockbusters vs Drama/Comedy TV', '2026-05-13T08:03:24.268144'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (471, 'Franchise‑linked titles vs standalone', '2026-05-15T07:49:57.145889'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (472, 'Non‑historical genre focus', '2026-05-15T07:35:10.606677'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (473, 'Comedy/drama TV episodes vs sci‑fi action movies', '2026-05-04T07:59:45.696814'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (474, 'Serious drama‑focused TV episodes', '2026-05-03T10:48:08.394496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (475, 'Adult crime/action TV episodes vs family movies', '2026-05-03T10:44:33.018740'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (476, 'Comedy‑centric productions', '2026-05-03T11:03:46.449553'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (477, 'Short episode runtime vs long feature runtime', '2026-05-09T07:56:09.668480'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (478, 'Adult-oriented Action/Crime and Documentary', '2026-05-03T10:28:41.332820'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (479, 'Short comedy sitcom episodes vs long sci‑fi dramas', '2026-05-14T09:08:12.673966'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (480, 'Standalone varied-genre works vs single-series comedy episodes', '2026-05-05T08:50:20.982379'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (481, 'Non‑science‑fiction vs science‑fiction', '2026-05-03T11:56:28.554092'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (482, 'Drama‑heavy, mystery/crime titles vs comedy‑focused', '2026-05-03T10:12:28.015643'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (483, 'Serious drama (historical/biographical) vs short comedy episodes', '2026-05-03T12:54:26.181767'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (484, 'Grounded drama/comedy (no sci‑fi/fantasy)', '2026-05-03T12:24:21.416229'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (485, 'Serious drama/Crime vs pure comedy', '2026-05-12T07:58:37.726589'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (486, 'Feature-length movies vs short TV episodes', '2026-05-03T10:58:47.388563'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (488, 'Non‑Sci‑Fi, primarily comedy or culturally grounded drama', '2026-05-11T07:36:11.055235'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (489, 'Speculative/fantasy settings vs grounded realism', '2026-05-03T11:32:49.139426'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (490, 'Non‑fiction music‑focused documentary episodes', '2026-05-03T11:17:01.779297'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (491, 'Stylized/fantasy/comedy genres vs realistic Western drama', '2026-05-03T13:00:19.307407'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (492, 'Guest star Adam Goldberg appearance', '2026-05-09T07:58:57.536375'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (493, 'Romance‑Comedy blend vs Action‑Crime focus', '2026-05-03T13:30:01.220570'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (494, 'Comedy‑heavy TV episodes vs drama/history episodes', '2026-05-03T12:00:23.982337'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (495, 'Genre‑blended TV episodes vs single‑genre movies', '2026-05-15T07:45:45.990599'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (496, 'Game or competition‑centric plot', '2026-05-03T13:21:23.029700'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (497, 'Lower critical rating vs higher-rated titles', '2026-05-08T07:47:47.226496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (498, 'Live-action comedy TV episodes', '2026-05-03T10:20:10.931224'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (499, 'Titles featuring cast member named Aaron', '2026-05-10T08:05:33.189244'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (500, 'Comedy‑centric titles', '2026-05-03T12:18:03.396799'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (501, 'Low-rated titles', '2026-05-03T10:31:14.688154'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (502, 'Romance genre present', '2026-05-15T07:32:13.760016'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (503, 'Crime/Mystery vs Action/Adventure', '2026-05-03T13:38:08.722538'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (504, 'Absence of thriller or mystery genre', '2026-05-14T08:15:55.454399'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (505, 'Action‑driven genre blend', '2026-05-13T08:06:15.148803'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (506, 'Low-rated titles vs high-rated titles', '2026-05-13T11:46:59.769691'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (507, 'TV episode‑centric titles', '2026-05-12T08:07:13.046815'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (508, 'Serious, non‑comedic genre focus', '2026-05-03T12:01:45.358385'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (509, 'Grounded Earth settings vs futuristic/space settings', '2026-05-13T08:13:35.735677'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (510, 'Real‑world drama episodes (non‑fantasy)', '2026-05-03T13:37:40.979448'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (511, 'Action‑Adventure/War focus vs teen romance', '2026-05-03T13:31:28.265749'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (512, 'Speculative or Documentary Genres', '2026-05-03T10:42:18.907574'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (513, 'Contemporary real-world settings', '2026-05-14T07:58:30.216594'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (514, 'Action/History focus versus light comedy', '2026-05-09T07:55:22.329285'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (515, 'Adventure‑focused, longer‑runtime episodes and movies', '2026-05-15T07:50:40.868421'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (516, 'Franchise/Series installment vs standalone title', '2026-05-05T08:52:55.339557'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (517, 'Includes Comedy genre', '2026-05-15T07:48:30.440911'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (519, 'Full-length film/season vs single episode', '2026-05-13T11:39:34.931615'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (520, 'Nautical or travel-themed titles', '2026-05-03T13:31:15.731890'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (521, 'Contemporary realistic settings vs fantastical/sci‑fi premises', '2026-05-13T08:07:36.298444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (524, 'Franchise theatrical movies vs TV episodes', '2026-05-09T09:06:06.576004'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (525, 'Comedy‑driven adventure/fantasy', '2026-05-03T09:54:36.638075'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (526, 'Gritty crime/drama focus vs family‑friendly content', '2026-05-12T07:54:08.695489'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (527, 'Short‑format comedy episodes', '2026-05-13T08:02:08.870349'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (528, 'Arts‑focused personal drama vs crime/sci‑fi settings', '2026-05-15T07:35:28.805370'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (529, 'Comedy, horror or adventure genre mix', '2026-05-14T09:18:54.393131'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (530, 'Animated short episodes vs live-action long formats', '2026-05-03T12:57:52.584832'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (531, 'Adult action/crime vs family comedy', '2026-05-03T12:33:18.889319'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (532, 'Adventure, Fantasy, or Historical setting', '2026-05-15T07:31:58.582976'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (533, 'Fictional narrative drama/comedy vs nature documentary', '2026-05-03T12:20:36.617158'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (534, 'Short‑format sitcom comedy episodes', '2026-05-14T09:00:03.698489'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (536, 'Horror or mystery genre blend', '2026-05-03T10:48:54.932432'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (537, 'Comedy/Biography dramas vs Action/Crime episodes', '2026-05-03T10:29:55.775814'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (538, 'Period or speculative setting vs modern realism', '2026-05-03T12:31:19.647913'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (539, 'Serious drama/scifi tone vs comedic/fantasy', '2026-05-03T10:14:38.473506'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (540, 'Comedy‑heavy titles vs serious drama titles', '2026-05-05T08:58:59.709698'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (541, 'Light‑hearted comedy focus', '2026-05-03T12:12:14.206604'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (542, 'Longer runtime (feature-length) vs short episodes', '2026-05-03T10:41:49.929144'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (543, 'Short sitcom comedy episodes', '2026-05-11T07:55:09.599287'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (544, 'Standalone TV episodes vs series/film releases', '2026-05-03T11:10:43.100712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (545, 'Adventure genre presence', '2026-05-14T08:18:50.215597'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (546, 'Adult‑oriented drama/thriller (no children focus)', '2026-05-03T12:30:26.573250'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (547, 'Comedy‑centric TV episodes', '2026-05-03T12:14:16.897683'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (548, 'Single-episode titles versus movies or seasons', '2026-05-03T11:27:27.340807'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (549, 'Non‑fiction/Educational vs Speculative Fiction Episodes', '2026-05-03T13:34:10.029584'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (550, 'Comedic/family-friendly content', '2026-05-10T08:14:39.403367'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (551, 'TV episodes versus feature-length movies', '2026-05-03T11:22:56.886711'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (552, 'Episodic TV focus vs standalone movies', '2026-05-03T12:23:49.070030'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (553, 'TV episodes vs feature films', '2026-05-03T09:32:09.369034'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (554, 'Action/Adventure with Comedy vs Straight Drama', '2026-05-03T11:28:56.475160'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (555, 'Crime‑free vs crime‑laden titles', '2026-05-14T09:18:27.154324'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (556, 'Political / real‑world focus', '2026-05-05T08:47:15.983742'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (557, 'Short non‑franchise episodes under one hour', '2026-05-03T11:23:50.364562'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (558, 'Adult‑oriented genre vs family animation', '2026-05-05T08:55:27.219025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (559, 'Animal‑centric nature documentaries (and family animal film)', '2026-05-12T08:00:16.947019'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (560, 'Crime‑drama episodes vs comedy‑centric titles', '2026-05-03T13:12:28.447278'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (562, 'Speculative adventure vs contemporary comedy/crime', '2026-05-03T11:07:23.754718'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (563, 'Feature-length / hour-long formats vs short episodes', '2026-05-14T08:20:03.558838'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (564, 'Absence of crime/mystery focus', '2026-05-03T12:01:30.603144'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (565, 'Feature-length theatrical movies vs TV episodes', '2026-05-03T12:00:59.200939'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (566, 'Short-form TV episodes vs feature-length movies', '2026-05-09T09:21:29.397579'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (568, 'Mainstream narrative blockbusters vs documentary/niche titles', '2026-05-03T09:52:33.483713'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (569, 'Personal character drama vs epic action/war', '2026-05-13T11:21:56.441780'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (570, 'Longer runtime focus', '2026-05-13T11:40:15.431486'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (571, 'Contemporary real‑world setting', '2026-05-11T08:03:58.972329'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (572, 'Music‑industry celebrity focus', '2026-05-03T12:23:19.064613'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (574, 'High-stakes adult action/drama vs light/reality', '2026-05-14T09:26:38.368353'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (575, 'Mixed-genre titles vs primarily comedy episodes', '2026-05-03T08:55:27.141162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (576, 'Long-form (≥45 min) titles vs short episodes', '2026-05-03T11:43:50.253534'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (578, 'High-action/espionage genre vs low-key comedy', '2026-05-03T12:01:12.632024'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (579, 'Creative‑profession centered stories', '2026-05-03T09:50:28.493525'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (582, 'TV episodes vs big-screen blockbusters', '2026-05-03T08:17:23.059563'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (583, 'Adult drama/tech focus vs family-friendly comedy', '2026-05-03T10:02:39.016632'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (584, 'Repeated series presence (Curb Your Enthusiasm)', '2026-05-03T12:32:24.393216'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (585, 'Contemporary work or school settings', '2026-05-03T10:00:17.881533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (586, 'Speculative/Adventure and Music Docs vs Real‑World Drama', '2026-05-03T10:19:55.424577'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (587, 'International or historical settings', '2026-05-03T12:28:35.047686'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (588, 'Serious Action/Drama/Thriller titles vs Light Comedy', '2026-05-03T12:19:26.064871'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (589, 'Lighthearted comedic adventure tone', '2026-05-03T13:19:38.495248'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (590, 'Features Crime or Mystery genre', '2026-05-03T10:00:41.932993'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (591, 'Serious crime/drama content vs light family/comedy', '2026-05-14T08:23:51.572407'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (592, 'Full movies/season entries vs single episodes', '2026-05-03T11:33:54.340152'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (594, 'Series with multiple entries vs single-episode titles', '2026-05-03T11:08:17.216208'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (595, 'Family-friendly comedy vs adult drama', '2026-05-03T13:03:45.589578'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (596, 'Speculative adventure/fantasy settings', '2026-05-14T09:17:29.083226'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (597, 'TV episodes without ratings vs rated movies', '2026-05-15T07:55:08.577817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (598, 'Includes thriller/horror/mystery elements', '2026-05-03T11:32:12.236454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (599, 'Historical/Adventure focus vs modern comedy', '2026-05-09T09:16:17.435788'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (600, 'Crime/History drama titles', '2026-05-03T12:53:24.584995'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (601, 'Comedy‑centric mainstream series vs serious drama', '2026-05-11T08:00:56.059376'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (602, 'Crime‑Drama/Thriller emphasis vs Adventure‑Animation focus', '2026-05-09T07:52:27.182388'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (603, 'Contains Adventure genre', '2026-05-09T09:19:51.048557'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (604, 'Franchise installment vs standalone title', '2026-05-12T07:59:06.070230'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (605, 'Standalone films/Shows vs Sitcom episode franchise', '2026-05-03T12:53:52.648385'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (606, 'Action‑driven violent mercenary focus', '2026-05-03T12:22:04.428107'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (607, 'Comedy-focused titles vs dramatic titles', '2026-05-03T11:36:18.040389'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (608, 'Epic franchise/event titles vs sitcom/low‑budget fare', '2026-05-03T09:56:02.357114'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (609, 'Single-episode comedy/romance vs full crime seasons', '2026-05-03T09:55:13.805320'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (610, 'Adult crime/action drama vs light comedy/fantasy', '2026-05-10T08:15:48.903258'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (611, 'Single-episode entries vs multi-episode seasons', '2026-05-15T07:41:38.246459'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (612, 'Longer, drama‑centric episodes (≈40‑50 min)', '2026-05-09T07:50:44.557939'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (614, 'Adult live-action drama with comedy/crime/horror blends', '2026-05-03T13:26:07.913093'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (615, 'Runtime 60 minutes or longer', '2026-05-06T07:49:36.872803'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (616, 'Adventure/Nature‑focused genres', '2026-05-11T08:07:35.331473'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (617, 'Comedy-focused TV episodes', '2026-05-13T11:30:49.316872'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (618, 'Fictional scripted titles vs documentary/reality', '2026-05-03T13:26:57.480550'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (619, 'Short sitcom comedy episodes', '2026-05-04T07:46:32.225014'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (620, 'Live‑action TV drama/mystery episodes', '2026-05-03T12:03:52.141252'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (621, 'Drama with high‑concept genres (fantasy, sci‑fi, history)', '2026-05-15T07:54:51.553038'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (622, 'Historical period drama/action', '2026-05-11T07:56:50.645061'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (623, 'Romance‑centric titles vs action‑heavy titles', '2026-05-14T08:20:25.617134'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (624, 'Family/Comedy adventure tone vs dark crime thriller', '2026-05-03T13:28:26.259674'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (625, 'Adult drama/historical content vs children’s comedy', '2026-05-03T12:49:54.020383'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (626, 'Short-form TV comedy‑drama episodes vs feature films', '2026-05-03T10:12:15.018684'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (627, 'Action‑driven genre mix', '2026-05-05T07:45:53.743681'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (628, 'Fantasy/Sci‑Fi Adventure Genre', '2026-05-12T07:56:05.216378'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (629, 'Live-action drama episodes vs animated/comedy series', '2026-05-09T09:04:48.981585'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (630, 'Contemporary professional workplace focus', '2026-05-03T13:37:54.562851'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (631, 'Short-form comedic TV episodes', '2026-05-03T13:06:54.570737'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (632, 'Adult crime/political drama episodes vs family content', '2026-05-15T07:40:46.982325'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (633, 'Feature-length movies vs short TV episodes', '2026-05-03T09:46:32.001613'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (634, 'Presence of Crime/Action/Fantasy genre', '2026-05-12T08:06:36.022720'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (635, 'Contemporary adult ensemble drama/comedy', '2026-05-13T08:12:27.314163'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (636, 'Contemporary real-world setting vs speculative fantasy setting', '2026-05-15T07:54:35.075650'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (637, 'Includes feature-length movies', '2026-05-03T08:51:05.120153'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (638, 'Animated or documentary‑style titles', '2026-05-03T11:23:12.365488'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (639, 'Serious historical/speculative drama vs light‑hearted romance/comedy', '2026-05-14T08:12:14.689041'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (641, 'Fantasy/Horror vs Light Comedy', '2026-05-07T07:57:16.671917'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (643, 'Speculative Dystopian Drama Episodes', '2026-05-03T13:10:59.568933'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (645, 'Standard ~45‑minute TV episode length', '2026-05-12T08:03:28.951655'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (647, 'Non‑comedy genre blend (action, crime, sci‑fi, bio)', '2026-05-07T07:53:19.437321'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (649, 'Serious drama‑oriented productions vs light comedy/animation', '2026-05-14T09:14:46.553399'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (650, 'Speculative genre (fantasy, sci‑fi, prehistoric)', '2026-05-03T12:51:22.323136'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (651, 'Mystery and horror genre blend', '2026-05-03T12:46:47.606641'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (652, 'TV episode length vs blockbuster movie length', '2026-05-03T10:17:58.168308'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (653, 'Drama‑Mystery genre focus', '2026-05-03T10:40:09.194709'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (654, 'Feature-length movies vs short TV episodes', '2026-05-10T08:20:36.662920'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (655, 'TV episodes vs feature films', '2026-05-07T07:39:59.520146'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (656, 'Action/Crime/Sci‑Fi episodes vs Comedy/Romance content', '2026-05-03T12:19:00.382014'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (657, 'Recent adult comedy/crime/action titles', '2026-05-03T12:41:30.868687'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (658, 'Comedy‑tagged titles vs non‑comedy titles', '2026-05-03T12:33:03.888433'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (659, 'Episode‑heavy titles vs feature‑film titles', '2026-05-03T11:52:12.719221'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (660, 'Short episodic crime dramas vs feature-length movies', '2026-05-08T07:40:41.983750'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (661, 'TV episode format', '2026-05-13T07:59:28.045454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (662, 'Grim dystopian/thriller tone', '2026-05-14T08:19:43.345706'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (664, 'Adult drama/crime TV episodes (no comedy)', '2026-05-03T10:47:31.290895'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (665, 'Speculative genre‑bending titles', '2026-05-14T09:19:19.987528'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (666, 'Mainstream non‑genre drama/comedy', '2026-05-03T13:10:11.462092'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (667, 'Mature crime/drama focus vs child/comedy focus', '2026-05-12T07:33:20.551181'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (668, 'Lacks Action‑Adventure genre', '2026-05-13T11:35:24.372411'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (669, 'Feature-length movies vs TV episodes', '2026-05-03T12:26:01.855151'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (670, 'Action/Adventure/Fantasy genre presence', '2026-05-14T09:19:54.068069'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (671, 'Titles featuring cast or crew named Adam', '2026-05-15T07:52:55.663880'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (672, 'Comedy/Adventure tone vs Historical/Drama tone', '2026-05-03T11:07:08.251032'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (673, 'Action‑focused titles vs non‑action episodes', '2026-05-03T10:25:10.154672'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (674, 'Institutional/Corporate setting focus', '2026-05-05T08:58:43.144934'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (675, 'Episode‑length TV content', '2026-05-15T07:56:25.128989'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (676, 'One-off films/specials vs ongoing series episodes', '2026-05-10T08:17:00.004806'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (677, 'Adaptations of real/historical or existing IP', '2026-05-03T13:42:23.282765'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (678, 'Colon‑separated subtitle titles', '2026-05-03T10:56:00.253741'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (679, 'Drama with thriller/mystery elements', '2026-05-03T09:57:36.837155'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (680, 'Includes cast member named Aaron', '2026-05-15T07:44:41.698619'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (682, 'Contemporary comedy‑drama/crime vs speculative sci‑fi mystery', '2026-05-12T08:04:50.795720'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (683, 'Comedy genre inclusion', '2026-05-03T10:34:37.468454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (684, 'Hybrid multi-genre blends', '2026-05-15T07:36:55.809241'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (685, 'Recent releases (2023+) vs older titles', '2026-05-03T11:34:47.691856'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (686, 'TV crime/drama episodes vs feature-length comedies', '2026-05-03T12:29:18.440867'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (687, 'Serious speculative drama vs light comedy', '2026-05-03T09:57:52.469681'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (688, 'Action/Comedy or Crime blend vs Drama/Mystery', '2026-05-10T08:07:50.855742'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (689, 'Includes season or movie formats', '2026-05-03T10:58:13.432122'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (690, 'Comedy TV episodes (under hour)', '2026-05-06T07:47:15.016647'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (691, 'Sci‑fi / mystery emphasis vs action‑adventure', '2026-05-03T10:46:23.449521'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (692, 'Comedy sitcom episodes vs Action drama movies', '2026-05-11T21:16:36.172900'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (693, 'Long genre‑mix adventure films vs short sitcom episodes', '2026-05-15T07:31:06.190064'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (695, 'Mystery genre presence', '2026-05-03T10:36:21.732630'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (697, 'Emphasis on action/combat vs drama/romance', '2026-05-03T12:36:24.000623'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (698, 'Mainstream adventure/fantasy blockbusters vs adult TV comedies', '2026-05-07T07:55:36.855352'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (699, 'Realistic drama/thriller settings vs fantasy/comedy', '2026-05-03T11:55:19.201992'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (700, 'Tech‑driven sci‑fi drama', '2026-05-03T12:59:49.410702'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (701, 'TV episodes vs feature films', '2026-05-15T07:53:19.570422'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (702, 'Series episode format vs standalone film', '2026-05-03T10:21:34.239456'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (703, 'Standalone TV episodes vs franchise‑linked titles', '2026-05-14T08:13:33.494518'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (704, 'Speculative genre vs realistic drama/comedy', '2026-05-12T07:41:46.367003'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (705, 'Period or speculative setting', '2026-05-05T07:59:52.758287'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (706, 'Dark drama/crime tone vs light comedy', '2026-05-03T13:27:38.841950'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (707, 'Feature films vs TV episodes', '2026-05-03T13:37:08.233120'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (708, 'Serious adult drama TV episodes', '2026-05-03T10:27:09.379623'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (709, 'Sci‑fi action‑adventure titles', '2026-05-03T13:06:41.370964'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (710, 'Predominantly Comedy titles', '2026-05-03T13:05:25.120776'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (711, 'Predominantly Action‑genre titles', '2026-05-13T07:47:09.357815'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (712, 'Theatrical feature films vs TV episodes', '2026-05-03T12:04:37.078466'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (713, 'Adventure‑genre titles', '2026-05-03T10:39:55.091354'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (714, 'Adventure genre presence', '2026-05-03T11:53:26.137444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (715, 'Low-rated titles (rating ≤ 5)', '2026-05-03T11:34:29.141270'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (716, 'Documentary/biography focus', '2026-05-09T07:51:23.038975'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (717, 'Comedy genre present', '2026-05-03T13:03:15.505973'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (718, 'Serious genre‑intense titles vs light comedy', '2026-05-03T13:18:49.180813'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (719, 'Drama blended with crime/fantasy/mystery', '2026-05-13T11:34:36.558701'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (720, 'Short runtime (under 100 minutes)', '2026-05-03T09:54:56.669034'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (721, 'Superhuman or speculative ability premise', '2026-05-03T12:17:00.380841'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (722, 'TV episodes vs feature films', '2026-05-03T13:01:34.091782'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (723, 'Sitcom comedy episodes vs sci‑fi action drama', '2026-05-03T09:47:09.308220'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (724, 'Workplace/Industry-focused content', '2026-05-07T07:47:36.373109'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (725, 'Primarily Drama genre titles', '2026-05-03T12:26:33.224399'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (727, 'Hour‑long drama series episodes', '2026-05-03T12:14:59.556059'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (729, 'Includes Action, Crime, Sci‑Fi or Fantasy genres', '2026-05-03T13:40:05.202191'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (730, 'Family‑friendly vs Adult Drama', '2026-05-03T11:20:34.965025'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (731, 'Action/Adventure or Crime focus', '2026-05-15T07:39:04.037354'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (733, 'Crime‑focused TV episodes vs documentary/biopic', '2026-05-03T12:17:13.232384'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (734, 'Grounded live‑action drama/comedy', '2026-05-09T07:53:40.234155'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (735, 'Adult TV episodes vs feature-length movies', '2026-05-12T08:01:25.409208'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (736, 'TV episode titles vs feature films', '2026-05-14T08:02:00.453864'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (737, 'Non‑comedic genres (action, documentary, music)', '2026-05-14T08:21:49.757170'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (738, 'Drama‑focused serious content vs comedy‑heavy features', '2026-05-03T13:06:16.477194'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (739, 'Non‑comedy drama or adventure titles', '2026-05-05T08:54:37.661478'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (740, 'Action/Adventure/Thriller genre focus', '2026-05-13T08:05:36.497488'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (741, 'High critical rating (8+)', '2026-05-03T10:47:17.411836'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (744, 'Light‑hearted romance/comedy vs serious drama', '2026-05-03T11:36:45.529084'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (745, 'Serious historical/biographical drama', '2026-05-03T13:40:43.239826'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (746, 'Comedy‑centric TV episodes', '2026-05-06T07:57:08.104972'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (747, 'Present‑day human‑focused stories', '2026-05-03T11:14:52.642022'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (748, 'Comic‑book / superhero franchise titles', '2026-05-08T08:02:43.712727'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (749, 'Youth‑oriented comedy/fantasy vs adult drama/sport', '2026-05-03T13:39:33.576591'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (750, 'Space‑based or futuristic sci‑fi setting', '2026-05-13T07:54:10.217772'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (751, 'Standalone non‑franchise episodes', '2026-05-03T11:17:48.502941'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (753, 'Anthology/limited series episodes vs ongoing series', '2026-05-03T13:08:40.822830'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (754, 'Titles featuring a character name', '2026-05-09T07:53:26.217501'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (757, 'Comedy‑centric titles', '2026-05-03T13:22:16.393392'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (758, 'Comedy genre presence', '2026-05-08T07:59:40.653109'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (761, 'Drama combined with high‑stakes genre (crime, thriller, sport, horror)', '2026-05-15T07:43:38.496539'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (762, 'Grounded live-action drama/comedy', '2026-05-03T12:29:54.688076'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (763, 'Action‑Adventure/Crime drama with longer runtimes', '2026-05-03T11:17:18.930770'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (764, 'Feature-length movies vs single TV episodes', '2026-05-03T13:35:04.350380'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (765, '22‑minute sitcom episodes vs longer formats', '2026-05-03T13:02:17.837454'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (767, 'Romance/fantasy‑tinged comedy‑drama episodes vs crime/action titles', '2026-05-13T07:52:15.502544'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (768, 'Action‑Crime movies over TV episodes', '2026-05-03T10:37:39.710020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (769, 'Literary/True‑Story Adaptation Preference', '2026-05-03T11:45:04.402462'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (770, 'Feature films over TV episodes', '2026-05-03T10:14:25.549962'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (771, 'Preference for offbeat, genre‑blending niche titles', '2026-05-03T10:08:43.613329'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (772, 'Preference for action‑crime thriller mashups', '2026-05-03T12:59:32.903706'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (773, 'Drama paired with mystery, crime, or comedy', '2026-05-03T11:57:45.786915'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (774, 'Grounded drama/comedy over high‑concept action', '2026-05-13T07:57:51.580178'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (775, 'Short-form comedy-drama episodes', '2026-05-03T12:44:13.958700'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (776, 'High‑octane action/crime vs low‑key romance/drama', '2026-05-07T07:47:20.706656'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (777, 'American‑centric biopics and high‑concept action', '2026-05-14T09:13:23.876966'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (778, 'Preference for lighter‑toned character‑drama', '2026-05-03T11:28:30.205671'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (779, 'Prefers feature films over episodic TV', '2026-05-03T12:37:03.181518'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (780, 'Drama‑centric TV episodes vs action/ documentary movies', '2026-05-05T07:49:28.384489'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (781, 'Female‑lead feature films', '2026-05-12T07:50:25.956377'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (782, 'Romance‑drama and music‑centric titles', '2026-05-03T13:08:21.712332'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (783, 'Romance‑centric content preference', '2026-05-03T13:23:14.303020'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (784, 'Grounded niche‑drama episodes over mainstream action/biopic', '2026-05-03T11:51:31.611371'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (785, 'Preference for comedic action‑adventure titles', '2026-05-03T13:24:20.159062'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (788, 'Fictional narrative drama over documentary/spectacle', '2026-05-03T13:41:19.694716'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (790, 'Fictional narrative movies over documentary/biopic content', '2026-05-03T12:09:57.305078'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (791, 'Adult‑oriented, high‑concept, star‑driven titles', '2026-05-03T12:27:05.692218'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (793, 'Non‑romantic genre‑driven titles', '2026-05-03T09:28:08.325625'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (794, 'High‑octane action/crime thrillers', '2026-05-03T13:40:52.127712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (796, 'Preference for drama/biography over crime thrillers', '2026-05-03T13:41:05.221798'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (799, 'TV episodes over movies', '2026-05-03T12:54:50.703287'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (800, 'Action/Thriller preference over Romance‑Drama', '2026-05-03T13:12:00.544015'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (801, 'Contemporary realistic drama/thriller', '2026-05-13T08:10:50.199875'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (802, 'TV episodes over feature films', '2026-05-14T08:13:07.979194'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (806, 'TV episodes & music documentaries over mainstream films', '2026-05-03T12:09:31.720831'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (807, 'Preference for star‑powered mainstream blockbusters', '2026-05-06T07:32:34.746060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (808, 'Action‑heavy, genre‑mix blockbusters', '2026-05-03T13:08:14.001661'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (809, 'Female‑lead focused titles', '2026-05-14T08:09:50.349584'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (810, 'Drama‑centric titles', '2026-05-04T07:41:00.633050'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (811, 'Short romance‑drama TV episodes vs feature films', '2026-05-03T12:47:59.669574'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (812, 'Genre‑blended crime/comedy over pure drama', '2026-05-03T13:19:59.942054'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (813, 'Artistic‑centric creative‑process narratives', '2026-05-09T07:56:26.689273'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (817, 'Workplace‑focused drama/comedy and real‑life stories', '2026-05-03T10:30:38.875475'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (819, 'Prefers TV episodes rather than feature films', '2026-05-03T09:38:20.171973'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (821, 'Feature films over documentaries and TV episodes', '2026-05-06T08:01:20.160218'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (823, 'Female‑centric contemporary genre‑blend entertainment', '2026-05-03T13:12:44.660605'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (824, 'Comedy-focused, light-tone entertainment', '2026-05-03T12:54:13.363049'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (825, 'Star‑driven Hollywood feature movies', '2026-05-03T13:12:36.667162'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (827, 'Prefers episodic TV content over standalone movies', '2026-05-03T13:32:21.538444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (828, 'Preference for high‑octane contemporary action‑comedy thrillers', '2026-05-03T12:17:20.387895'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (829, 'Prefers action/comedy and sport over romance/musical', '2026-05-03T12:00:00.361060'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (831, 'Contemporary dramedy and real‑world documentary preference', '2026-05-12T08:06:46.657214'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (834, 'Preference for serious drama over comedy', '2026-05-03T13:42:06.044533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (835, 'Mainstream action‑comedy blockbusters', '2026-05-03T11:29:09.096837'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (836, 'TV drama episodes over movies', '2026-05-03T12:11:46.192813'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (838, 'Action‑heavy, crime‑focused thrillers', '2026-05-03T13:36:08.015173'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (840, 'TV episodes over feature films', '2026-05-03T10:18:09.122173'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (841, 'Movies over TV episodes', '2026-05-08T08:01:39.750945'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (844, 'High‑energy action/comedy‑crime blends', '2026-05-03T13:18:34.859671'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (845, 'Prefers brand‑new 2025‑2026 releases', '2026-05-03T12:35:20.752493'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (846, 'Gritty crime & high‑stakes drama preference', '2026-05-14T09:20:18.020444'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (847, 'Original contemporary films over adaptations and sequels', '2026-05-03T13:31:57.522861'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (855, 'Spectacle‑driven, high‑energy entertainment', '2026-05-14T09:06:14.149341'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (858, 'Serious adult drama and crime preference', '2026-05-11T08:01:16.490532'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (859, 'TV episode dramedy preference', '2026-05-03T11:57:35.667212'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (860, 'Light‑hearted comedy/romance over serious biopic', '2026-05-03T13:14:45.705078'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (861, 'Preference for TV episodes over movies', '2026-05-03T12:48:50.478780'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (864, 'Prefers TV episodes with drama‑comedy blends', '2026-05-12T07:38:06.774345'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (865, 'Fictional narrative films vs nonfiction biopic/documentary', '2026-05-14T08:24:42.718284'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (866, 'Franchise/celebrity‑linked titles', '2026-05-03T11:19:06.280834'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (867, 'Thriller‑action over drama/romance', '2026-05-14T07:57:24.359519'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (869, 'Gritty crime/action thrillers over lighter fare', '2026-05-03T08:39:36.764009'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (871, 'Real-world adult drama over musical/teen fare', '2026-05-03T13:17:14.728661'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (872, 'Preference for lower‑rated recent titles', '2026-05-12T07:35:27.926407'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (875, 'Movies over TV episodes', '2026-05-03T11:57:20.162738'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (876, 'Preference for mainstream celebrity‑driven titles', '2026-05-03T13:35:55.121872'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (884, 'Adult-oriented drama over pop/teen spectacle', '2026-05-03T10:01:39.803268'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (886, 'Preference for adult drama over light comedy/family', '2026-05-05T08:59:30.758004'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (887, 'Pop‑culture, genre‑blended contemporary releases', '2026-05-03T13:27:08.211384'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (890, 'High‑energy genre‑mix and pop‑culture titles', '2026-05-03T11:31:45.906377'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (895, 'Action‑heavy, comedy & music spectacle fans', '2026-05-03T12:31:48.393898'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (903, 'Pop‑culture spectacle and action titles', '2026-05-06T08:00:33.341380'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (904, 'Gritty adult crime and drama preference', '2026-05-03T12:35:13.393480'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (906, 'Loves action‑heavy, comedic and music‑concert titles', '2026-05-03T11:19:28.359564'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (911, 'Preference for crime/mystery‑thriller blends', '2026-05-03T12:43:18.632866'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (912, 'Crime‑thriller and genre‑blend TV episodes', '2026-05-03T11:31:37.342077'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (913, 'Profession‑centric dramedy & action titles', '2026-05-03T13:14:14.364169'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (914, 'Preference for standalone feature films', '2026-05-06T07:48:49.594016'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (915, 'Romance‑driven, non‑action, real‑life or literary adaptations', '2026-05-03T13:36:16.650262'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (917, 'Music and literary adaptation preference', '2026-05-03T13:38:48.013344'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (921, 'Arts‑centric narratives (music, food, literary romance)', '2026-05-10T08:07:08.406831'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (926, 'Mystery & Thriller over Light Comedy/Historical Romance', '2026-05-03T13:34:32.209576'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (927, 'Prefers drama/biography and spectacle over crime/sport', '2026-05-14T09:16:30.738412'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (930, 'Non‑violent, character‑driven mainstream titles', '2026-05-03T13:33:22.096396'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (932, 'Action‑heavy, genre‑mix (crime/comedy) preference', '2026-05-03T11:06:14.899077'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (933, 'Contemporary real‑world and biographical titles', '2026-05-14T09:25:03.026514'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (936, 'Big-budget star-driven theatrical movies', '2026-05-09T07:42:34.901139'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (943, 'Prefers high‑intensity action/thriller films', '2026-05-15T07:45:54.992471'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (944, 'Preference for prestige dramas and real-life biopics', '2026-05-03T13:30:49.515326'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (947, 'Romance‑focused drama over action/thriller', '2026-05-03T12:27:26.985496'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (954, 'Light‑hearted comedy‑driven recent movies and TV episodes', '2026-05-03T12:59:56.177376'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (955, 'Crime & Mystery Preference', '2026-05-03T13:31:38.718426'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (957, 'Comedy & music‑focused titles over serious drama', '2026-05-11T07:42:53.413663'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (958, 'Likes high‑stakes competition and performance dramas', '2026-05-13T11:33:50.374556'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (960, 'Grounded character drama over action‑comedy spectacle', '2026-05-03T10:43:25.243333'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (961, 'Action/Crime and Real‑World Documentary Preference', '2026-05-03T11:29:19.208624'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (963, 'Mystery‑Crime Thriller Preference', '2026-05-13T11:47:59.155492'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (964, 'Action‑focused genre blockbusters', '2026-05-03T10:54:28.721281'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (965, 'Upbeat mainstream titles over gritty crime dramas', '2026-05-03T12:04:47.204821'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (966, 'Preference for niche genre‑blend indie dramas', '2026-05-09T09:09:56.878708'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (968, 'Recent theatrical movies vs TV episodes', '2026-05-07T07:32:16.956416'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (972, 'Preference for Drama over Comedy', '2026-05-03T13:25:48.789423'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (976, 'Adult‑oriented high‑stakes drama/action', '2026-05-03T13:33:31.205104'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (980, 'Action‑Crime/Thriller over Real‑Life Drama', '2026-05-03T10:42:29.092297'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (981, 'Feature-length mainstream cinema over short TV episodes', '2026-05-10T08:00:36.134793'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (982, 'Fictional action/crime and comedy over real-life docs', '2026-05-14T09:20:05.248549'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (983, 'Prefers scripted fiction over documentary/real-life content', '2026-05-13T11:25:36.864228'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (985, 'Preference for feature films over TV episodes', '2026-05-03T11:44:28.219901'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (986, 'Franchise/Series installments over standalone films', '2026-05-14T09:17:48.778611'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (989, 'Action‑heavy, genre‑blend movies vs episodic dramas', '2026-05-03T09:56:49.065712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (990, 'Romance and comedy‑focused light entertainment', '2026-05-03T13:41:48.972533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (999, 'High‑octane thriller/action preference', '2026-05-14T09:11:22.178791'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1001, 'Modern gritty action/thriller preference', '2026-05-15T07:37:04.138329'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1008, 'Contemporary pop‑culture & music docs vs classic dramas', '2026-05-13T11:36:11.008172'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1009, 'Contemporary high‑tension or workplace‑centric titles', '2026-05-09T07:38:58.168324'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1013, 'Spectacle‑driven action/comedy vs character‑drama', '2026-05-09T09:02:40.425882'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1014, 'Lighthearted comedy‑drama titles', '2026-05-04T07:47:57.108104'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1016, 'Female‑centered narratives', '2026-05-04T08:02:17.659289'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1018, 'TV episode comedy/mystery over feature films', '2026-05-05T07:47:40.370781'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1020, 'High‑energy genre blends (action, comedy, sci‑fi)', '2026-05-05T08:59:43.071612'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1021, 'Action/Thriller over Biopic/Musical', '2026-05-14T09:06:55.494029'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1022, 'Gritty action‑thriller crime titles', '2026-05-13T11:31:26.138686'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1024, 'Modern pop‑culture, high‑energy entertainment', '2026-05-03T12:45:26.596133'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1026, 'Preference for high‑profile star‑led mainstream releases', '2026-05-03T12:24:09.194419'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1027, 'Action‑Comedy Film Preference', '2026-05-03T13:02:02.470479'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1032, 'Real-life drama & romance over light comedy', '2026-05-03T12:24:41.420259'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1037, 'Prefers feature-length dramatic movies over episodes/documentaries', '2026-05-03T09:52:42.626935'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1038, 'Gritty drama TV episodes over mainstream movies', '2026-05-03T13:26:30.081343'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1043, 'Workplace‑oriented drama preference', '2026-05-05T07:59:18.913693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1045, 'Preference for quirky genre‑blends and indie dramedies', '2026-05-03T13:12:55.391996'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1053, 'Preference for character-driven drama and period pieces', '2026-05-14T09:10:45.211616'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1054, 'High‑concept genre movies over episodic dramas', '2026-05-03T11:33:27.446101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1059, 'Shorter runtime, episode & documentary focus', '2026-05-03T10:11:01.824741'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1060, 'Workplace/Industry Insider Stories', '2026-05-03T13:14:07.246330'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1061, 'Feature-length movies vs short TV episodes', '2026-05-10T08:06:59.008922'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1065, 'Preference for low‑rated niche genre titles', '2026-05-03T10:22:20.419314'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1074, 'Lighthearted dramedy & music over gritty action/crime', '2026-05-09T09:07:34.726853'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1077, 'Fans of 2025 releases', '2026-05-03T13:30:18.258063'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1080, 'Short-form dramedy & mystery episodes', '2026-05-03T13:19:10.658901'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1082, 'Thriller and action‑focused titles', '2026-05-15T07:48:40.771387'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1086, 'Serious drama & thriller preference', '2026-05-13T08:03:53.429560'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1087, 'Preference for intimate drama over spectacle', '2026-05-15T07:44:10.431749'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1088, 'Profession‑centric drama & documentary titles', '2026-05-03T12:08:27.412846'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1090, 'Prefers genre‑blended drama/comedy over crime‑thrillers', '2026-05-14T08:57:26.823335'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1092, 'High‑stakes competition and conflict narratives', '2026-05-13T11:40:34.498758'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1096, 'Contemporary high‑energy genre mix', '2026-05-03T10:29:06.983329'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1099, 'Prefers drama/comedy, avoids action‑thriller', '2026-05-13T08:05:54.047087'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1101, 'Female‑focused drama/comedy series and music docs', '2026-05-03T13:42:29.828214'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1104, 'Preference for TV episodes over movies', '2026-05-03T13:07:17.963783'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1105, 'Fictional genre‑blend narratives over real‑life documentaries', '2026-05-05T09:02:17.822907'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1108, 'Prefers contemporary pop‑culture and high‑concept genres', '2026-05-03T13:22:50.025946'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1110, 'Long feature films vs short episodes', '2026-05-15T07:46:44.990358'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1113, 'Prefers contemporary pop‑culture spectacle and mixed‑tone shows', '2026-05-08T07:37:54.816205'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1118, 'Prefers TV episodes over feature films', '2026-05-11T08:03:37.263714'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1120, 'Drama‑centric, character‑driven titles', '2026-05-12T08:03:48.904853'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1125, 'Action‑heavy, comedic spectacle preference', '2026-05-03T12:53:09.691817'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1126, 'Preference for narrative feature films over documentaries/TV', '2026-05-14T08:17:47.518901'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1128, 'Niche genre‑blends over mainstream drama', '2026-05-15T07:49:11.496231'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1138, 'Preference for crime‑mystery dramas over romance‑history', '2026-05-03T10:39:26.456091'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1141, 'Fictional narrative preference over documentary/real‑life', '2026-05-15T07:36:21.357276'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1149, 'Serious drama & crime over light/comedy & docu', '2026-05-03T10:40:59.860954'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1150, 'Preference for nonfiction biographical/documentary titles', '2026-05-13T11:31:19.942212'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1160, 'High‑concept action/adventure and pop‑culture titles', '2026-05-03T13:00:04.635776'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1164, 'Preference for high‑energy performance‑centric titles', '2026-05-03T13:20:13.626975'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1166, 'Spectacle‑heavy action, music, and comedy titles', '2026-05-03T11:23:58.211805'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1176, 'Prestige, high‑rated titles vs low‑rated genre fare', '2026-05-13T08:06:14.872683'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1177, 'Mainstream narrative crime/action/comedy titles', '2026-05-03T11:54:58.462453'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1181, 'Action‑Comedy/Crime genre preference', '2026-05-03T13:00:53.991609'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1184, 'Workplace‑centric drama/comedy preference', '2026-05-05T08:59:53.333238'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1187, 'Action‑thriller crime preference', '2026-05-13T11:29:44.034404'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1192, 'Grounded character-driven drama', '2026-05-03T12:56:25.059962'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1196, 'Biopic & dramedy focus, avoids high‑action thrillers', '2026-05-15T07:51:58.494798'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1200, 'Prefers genre‑mashup feature films over biopic/comedy episodes', '2026-05-03T13:10:37.032175'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1206, 'Preference for drama/romance over action-thriller', '2026-05-09T07:35:42.417627'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1209, 'Youth‑centric pop‑culture comedy/romance', '2026-05-03T13:25:25.734574'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1211, 'Preference for big‑budget, star‑driven feature films', '2026-05-03T12:08:58.280497'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1212, 'Preference for grounded biographical and sports dramas', '2026-05-14T09:11:55.189860'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1221, 'Comedy‑action/crime genre blend', '2026-05-03T12:09:22.198652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1222, 'High‑energy genre‑blend action/adventure films', '2026-05-03T11:21:51.455009'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1223, 'High‑octane action‑thriller and crime blends', '2026-05-03T12:40:04.061370'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1224, 'Real‑world biopic/music docs vs fantasy/animation', '2026-05-13T11:27:24.385744'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1228, 'Action‑Crime movies vs music/TV episodes', '2026-05-03T10:56:44.409566'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1229, 'Modern genre‑mixes vs classic period dramas', '2026-05-13T11:37:26.550973'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1230, 'Prefers comedy‑action and light‑hearted series', '2026-05-03T12:58:41.750174'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1231, 'Fans of high‑energy action‑crime thrillers', '2026-05-07T07:38:14.402737'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1237, 'Preference for recent standalone releases', '2026-05-03T11:53:39.580772'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1241, 'Short‑form dramedy episodes with personal relationships', '2026-05-03T11:08:25.144656'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1243, 'Preference for episodic TV over feature films', '2026-05-03T10:33:09.316959'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1245, 'Preference for genre‑blending, pop‑culture spectacles', '2026-05-03T13:34:50.265868'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1251, 'Preference for action and real‑world performance titles', '2026-05-11T07:59:16.026280'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1254, 'Crime‑centric film preference', '2026-05-03T10:24:52.122138'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1255, 'Female‑lead focused titles', '2026-05-03T13:33:12.609859'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1256, 'Romance‑centric genre blends', '2026-05-10T08:03:23.209190'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1257, 'Crime‑Mystery and Romance‑Heavy Drama Preference', '2026-05-03T13:35:41.292907'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1259, 'Music‑centric and performance‑driven titles', '2026-05-03T13:39:07.971833'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1261, 'Low‑rated recent genre‑blend releases', '2026-05-03T10:04:47.037712'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1265, 'Music‑centric performance titles', '2026-05-03T13:22:58.327656'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1267, 'Serious drama & thriller over comedic titles', '2026-05-03T13:13:13.424416'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1268, 'Grounded character‑driven drama', '2026-05-06T07:49:13.194914'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1274, 'Gritty crime/thriller dramas vs music/romance', '2026-05-03T11:58:45.347200'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1275, 'Preference for genre‑blending titles', '2026-05-03T10:07:27.417652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1276, 'High‑octane action and crime thrillers', '2026-05-03T12:23:59.375757'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1279, 'Competitive/achievement-focused action and documentary', '2026-05-03T13:23:51.140070'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1281, 'Character-driven drama and music over action-thriller', '2026-05-07T07:36:23.957391'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1283, 'Low‑rated niche and documentary‑focused content', '2026-05-03T12:47:52.326033'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1284, 'Romance‑driven drama/comedy preference', '2026-05-03T08:20:12.128230'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1285, 'Contemporary drama and real‑world stories', '2026-05-14T08:02:16.061193'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1287, 'Grounded adult drama/thriller films', '2026-05-15T07:38:43.704101'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1288, 'Crime & Mystery Drama Preference', '2026-05-03T13:26:21.611899'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1289, 'Preference for drama/romance over action‑centric titles', '2026-05-03T13:07:49.376737'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1293, 'Prefers TV episodes over feature films', '2026-05-03T11:14:08.809993'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1294, 'Movies over TV episodes', '2026-05-05T08:50:30.616849'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1296, 'Prefers entertainment‑industry / performance titles', '2026-05-03T13:25:05.444102'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1298, 'Genre‑bending, high‑energy action‑adventure entertainment', '2026-05-03T13:10:45.896533'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1300, 'Male‑centered contemporary drama/competition', '2026-05-03T10:31:43.634161'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1307, 'Mainstream star‑driven films over niche/indie content', '2026-05-03T07:45:43.573853'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1315, 'Celebrity‑driven mainstream blockbusters and pop‑culture events', '2026-05-03T12:19:08.769732'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1317, 'Artistic/Character-driven over Gritty Action-Thrillers', '2026-05-13T08:13:51.006091'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1318, 'Profession‑focused dramas vs genre‑centric thrillers', '2026-05-03T12:15:38.891599'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1319, 'Fans of visual spectacle and music documentaries', '2026-05-09T09:08:36.467032'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1320, 'Profession‑centric drama & documentary preference', '2026-05-03T13:19:21.103275'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1321, 'Preference for genre‑blended, comedic‑drama TV episodes', '2026-05-09T07:50:06.721424'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1334, 'Preference for TV episodes over feature films', '2026-05-03T13:24:29.845483'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1337, 'Preference for short-form episodic content', '2026-05-15T07:34:54.043187'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1340, 'Preference for music‑centric titles', '2026-05-03T11:30:06.465034'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1347, 'Feature‑length dramatic movies', '2026-05-03T13:39:17.068902'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1356, 'Grim drama and thriller over light entertainment', '2026-05-03T12:57:35.789643'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1357, 'Workplace and professional setting stories', '2026-05-03T10:57:56.309173'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1361, 'Immersive, atmospheric settings over grounded realism', '2026-05-15T07:39:58.984118'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1365, 'Preference for music documentaries and light sci‑fi', '2026-05-13T08:03:35.209599'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1367, 'High‑octane action/crime thriller preference', '2026-05-03T09:40:30.092521'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1370, 'Conflict‑driven action & crime vs romance/celebration', '2026-05-03T11:47:50.580266'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1372, 'Scripted drama/comedy preference vs music docs', '2026-05-08T07:44:27.565716'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1375, 'Modern workplace‑focused drama', '2026-05-03T13:24:11.366238'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1380, 'Mystery‑action blended titles over pure romance/history', '2026-05-08T08:00:19.881740'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1382, 'Adult-oriented contemporary drama and action', '2026-05-03T12:12:57.508356'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1385, 'Occupation‑centric narratives', '2026-05-14T08:55:47.425648'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1393, 'Drama‑heavy title preference', '2026-05-03T12:58:19.648693'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1395, 'Action‑thriller and high‑energy spectacle fans', '2026-05-03T12:50:18.836427'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1400, 'Big‑budget star‑driven mainstream movies', '2026-05-03T11:02:40.690518'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1406, 'Personal Ambition in Performance or Extreme Settings', '2026-05-03T11:53:00.334775'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1416, 'Drama and biography focused titles', '2026-05-15T07:42:52.743622'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1417, 'Drama‑heavy romance/comedy titles', '2026-05-03T13:16:37.568977'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1418, 'Female‑led high‑action crime/thriller', '2026-05-03T10:55:11.037408'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1423, 'Comedy‑action genre blend', '2026-05-03T13:07:03.706260'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1427, 'Fans of music/comedy performance‑centric productions', '2026-05-03T10:40:51.332459'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1429, 'Pop‑culture and niche industry subject matter', '2026-05-12T07:38:39.542525'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1432, 'Drama‑centric content preference', '2026-05-07T07:42:36.470928'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1436, 'High‑energy pop‑culture spectacle titles', '2026-05-03T12:48:38.420783'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1441, 'Likes high‑stakes competition and performance‑driven films', '2026-05-03T11:50:38.374633'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1442, 'Preference for feature films over TV episodes', '2026-05-03T12:44:06.867081'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1443, 'Preference for contemporary real‑world / pop‑culture titles', '2026-05-11T07:48:03.320186'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1452, 'Serious drama preference, avoids comedy', '2026-05-07T07:52:18.160358'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1456, 'Prefers movies (feature‑length) vs TV episodes', '2026-05-13T08:02:44.898453'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1458, 'Drama‑heavy short episodes over long action films', '2026-05-08T07:38:35.758763'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1459, 'Preference for high‑energy action and spectacle films', '2026-05-03T13:16:46.140666'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1463, 'Crime/mystery/thriller focus', '2026-05-10T08:11:39.360879'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1465, 'Female‑centered high‑energy genre titles', '2026-05-03T13:34:41.497983'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1467, 'Thrill‑heavy & music docs vs straight dramas', '2026-05-14T09:06:23.907810'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1469, 'Drama & biography over action thrillers', '2026-05-15T07:51:49.803339'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1470, 'Artistic‑craft or performance‑focused narratives', '2026-05-03T12:18:43.758223'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1471, 'Preference for high‑stakes, conflict‑driven stories', '2026-05-03T11:59:18.299270'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1472, 'Short episodic comedy‑drama series', '2026-05-03T12:32:48.407193'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1474, 'Gritty crime/mystery over romance/music docs', '2026-05-03T12:26:56.216096'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1480, 'Character‑driven drama/comedy over high‑concept sci‑fi/documentary', '2026-05-15T07:57:19.927364'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1483, 'Prefers character‑driven drama over genre thrillers', '2026-05-13T11:18:12.841772'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1496, 'Character-driven drama over high‑octane action', '2026-05-03T11:59:49.562625'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1502, 'Workplace and real-life drama preference', '2026-05-03T12:41:40.190960'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1506, 'Prefers drama/comedy over action/crime', '2026-05-04T07:58:52.086059'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1509, 'Preference for high‑profile, mainstream, higher‑rated titles', '2026-05-03T12:15:27.430372'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1510, 'Character‑driven drama & indie TV episodes', '2026-05-14T09:03:57.050878'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1511, 'Romance/Drama preference, avoids crime‑heavy titles', '2026-05-03T12:49:39.388445'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1512, 'Comedy and music‑centric light entertainment', '2026-05-03T10:11:46.839652'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1516, 'Feature movies (action/crime/comedy) vs TV episodes', '2026-05-09T09:20:33.098011'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1523, 'Preference for romance/comedy/music‑centric titles', '2026-05-03T08:26:54.321919'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                

                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (1533, 'Fast‑paced genre blends (thriller/comedy) vs period/biopic', '2026-05-13T08:09:22.433360'::timestamp)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                
COMMIT;
