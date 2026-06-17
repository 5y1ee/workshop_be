-- ============================================================
-- 가평 워크샵 웹 프로젝트 DDL (PostgreSQL) — v5
-- ============================================================
-- v4 대비 변경 사항 (alembic 기준):
--   1) d4e5f6a1b2c3: 발언권 이벤트 테이블 신설
--      - speaking_events / speaking_submissions / speaking_tap_logs / speaking_grants
--      - 시즌당 open 이벤트 1건 부분 유니크 인덱스
--   2) e5f6a1b2c3d4: timetable.main_visible 추가 (메인 화면 노출 토글)
--   3) f6a1b2c3d4e5: seasons.gacha_pull_cost 추가 (뽑기 1회 차감 포인트)
--   4) a6b7c8d9e0f1: user_hidden_roles 시즌·유저 유니크 제약 추가
--   5) b7c8d9e0f1a2: 오프라인 게임 카탈로그 2종(팀/개인) — 데이터 시드 (스키마 변화 없음)
--   6) c8d9e0f1a2b3: timetable.score_mode 추가 (팀전/개인전 스코어보드 단위 오버라이드)
-- ============================================================

-- ------------------------------------------------------------
-- seasons
-- ------------------------------------------------------------
CREATE TABLE seasons (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'preparing',
    started_at      TIMESTAMP   NULL,
    ended_at        TIMESTAMP   NULL,
    gacha_pull_cost INT         NOT NULL DEFAULT 1,
    del_yn          BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by  INT             NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP       NULL,
    updated_by  INT             NULL,
    CONSTRAINT seasons_status_check CHECK (status IN ('preparing', 'active', 'done'))
);

-- ------------------------------------------------------------
-- users  (team_id 컬럼은 시즌별 멤버십 도입으로 제거됨)
-- ------------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50)     NOT NULL UNIQUE,
    password        VARCHAR(255)    NOT NULL,
    nickname        VARCHAR(50)     NOT NULL,
    role            VARCHAR(10)     NOT NULL,
    point           INT             NOT NULL DEFAULT 0,
    profile_image   VARCHAR(255)    NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT users_role_check CHECK (role IN ('admin', 'user'))
);

-- ------------------------------------------------------------
-- teams
-- ------------------------------------------------------------
CREATE TABLE teams (
    id          SERIAL PRIMARY KEY,
    season_id   INT             NOT NULL,
    name        VARCHAR(50)     NOT NULL,
    del_yn      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_teams_season FOREIGN KEY (season_id) REFERENCES seasons (id)
);

-- ------------------------------------------------------------
-- team_members (시즌별 팀 멤버십)
-- ------------------------------------------------------------
CREATE TABLE team_members (
    id          SERIAL PRIMARY KEY,
    season_id   INT             NOT NULL,
    team_id     INT             NOT NULL,
    user_id     INT             NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_team_members_season_user UNIQUE (season_id, user_id),
    CONSTRAINT fk_team_members_season FOREIGN KEY (season_id) REFERENCES seasons (id),
    CONSTRAINT fk_team_members_team   FOREIGN KEY (team_id)   REFERENCES teams (id),
    CONSTRAINT fk_team_members_user   FOREIGN KEY (user_id)   REFERENCES users (id)
);

-- ------------------------------------------------------------
-- 순환 참조 FK (users, seasons)
-- ------------------------------------------------------------
ALTER TABLE users
    ADD CONSTRAINT fk_users_updated FOREIGN KEY (updated_by) REFERENCES users (id);

ALTER TABLE seasons
    ADD CONSTRAINT fk_seasons_created FOREIGN KEY (created_by) REFERENCES users (id),
    ADD CONSTRAINT fk_seasons_updated FOREIGN KEY (updated_by) REFERENCES users (id);

-- ------------------------------------------------------------
-- game  ('tap' input_type 추가)
-- ------------------------------------------------------------
CREATE TABLE game (
    id                  SERIAL PRIMARY KEY,
    title               VARCHAR(100)    NOT NULL,
    description         TEXT            NULL,
    participant_type    VARCHAR(20)     NOT NULL,
    input_type          VARCHAR(20)     NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP       NULL,
    updated_by          INT             NULL,
    CONSTRAINT game_participant_type_check CHECK (participant_type IN ('team_vs', 'individual', 'team_internal', 'representative')),
    CONSTRAINT game_input_type_check       CHECK (input_type IN ('chat', 'button', 'offline', 'puzzle', 'vote', 'tap')),
    CONSTRAINT fk_game_updated FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- timetable
-- ------------------------------------------------------------
CREATE TABLE timetable (
    id              SERIAL PRIMARY KEY,
    season_id       INT             NOT NULL,
    game_id         INT             NOT NULL,
    phase           VARCHAR(50)     NULL,
    order_index     INT             NOT NULL,
    label           VARCHAR(100)    NULL,
    raffle_reward   INT             NOT NULL DEFAULT 0,
    main_visible    BOOLEAN         NOT NULL DEFAULT TRUE,
    score_mode      VARCHAR(20)     NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT timetable_score_mode_check CHECK (score_mode IN ('team', 'individual')),
    CONSTRAINT fk_timetable_season  FOREIGN KEY (season_id)  REFERENCES seasons (id),
    CONSTRAINT fk_timetable_game    FOREIGN KEY (game_id)    REFERENCES game (id),
    CONSTRAINT fk_timetable_updated FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- game_sessions
-- ------------------------------------------------------------
CREATE TABLE game_sessions (
    id              SERIAL PRIMARY KEY,
    timetable_id    INT             NOT NULL,
    state           VARCHAR(20)     NOT NULL DEFAULT 'idle',
    seed            VARCHAR(100)    NULL,
    started_at      TIMESTAMP       NULL,
    ended_at        TIMESTAMP       NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT game_sessions_state_check CHECK (state IN ('idle', 'ready', 'in_progress', 'scoring', 'reward', 'done')),
    CONSTRAINT fk_game_sessions_timetable FOREIGN KEY (timetable_id) REFERENCES timetable (id),
    CONSTRAINT fk_game_sessions_updated   FOREIGN KEY (updated_by)   REFERENCES users (id)
);

-- ------------------------------------------------------------
-- game_rounds  (세션 내부 라운드 진행도 + tap 게임 전용 컬럼)
-- ------------------------------------------------------------
CREATE TABLE game_rounds (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NOT NULL,
    order_index     INT             NOT NULL,
    status          VARCHAR(10)     NOT NULL DEFAULT 'waiting',
    prompt          TEXT            NULL,
    media_url       VARCHAR(255)    NULL,
    options         JSON            NULL,
    correct_answer  VARCHAR(255)    NULL,
    opened_at       TIMESTAMP       NULL,
    closed_at       TIMESTAMP       NULL,
    -- tap 게임 전용 ↓
    tap_mode        VARCHAR(10)     NULL,
    duration        INT             NULL,
    target_time     DOUBLE PRECISION NULL,
    signal_at       TIMESTAMP       NULL,
    -- ↑
    created_by      INT             NULL,
    updated_by      INT             NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    CONSTRAINT game_rounds_status_check    CHECK (status IN ('waiting', 'open', 'closed')),
    CONSTRAINT game_rounds_tap_mode_check  CHECK (tap_mode IS NULL OR tap_mode IN ('count', 'speed', 'timing')),
    CONSTRAINT uq_game_rounds_session_order UNIQUE (session_id, order_index),
    CONSTRAINT fk_game_rounds_session      FOREIGN KEY (session_id) REFERENCES game_sessions (id),
    CONSTRAINT fk_game_rounds_created_by   FOREIGN KEY (created_by) REFERENCES users (id),
    CONSTRAINT fk_game_rounds_updated_by   FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- round_submissions  (button/vote/tap-speed/tap-timing 1인 1답)
-- ------------------------------------------------------------
CREATE TABLE round_submissions (
    id          SERIAL PRIMARY KEY,
    round_id    INT             NOT NULL,
    user_id     INT             NOT NULL,
    answer      VARCHAR(255)    NOT NULL,
    is_correct  BOOLEAN         NOT NULL DEFAULT FALSE,
    server_time TIMESTAMP       NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_round_submissions_round_user UNIQUE (round_id, user_id),
    CONSTRAINT fk_round_submissions_round FOREIGN KEY (round_id) REFERENCES game_rounds (id),
    CONSTRAINT fk_round_submissions_user  FOREIGN KEY (user_id)  REFERENCES users (id)
);

-- ------------------------------------------------------------
-- tap_logs  (tap count 모드 개별 탭 기록)
-- ------------------------------------------------------------
CREATE TABLE tap_logs (
    id          SERIAL PRIMARY KEY,
    round_id    INT             NOT NULL,
    user_id     INT             NOT NULL,
    server_time TIMESTAMP       NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_tap_logs_round FOREIGN KEY (round_id) REFERENCES game_rounds (id),
    CONSTRAINT fk_tap_logs_user  FOREIGN KEY (user_id)  REFERENCES users (id)
);

-- ------------------------------------------------------------
-- game_score_logs
-- ------------------------------------------------------------
CREATE TABLE game_score_logs (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NOT NULL,
    subject_type    VARCHAR(10)     NOT NULL,
    subject_id      INT             NOT NULL,
    chat_log_id     INT             NULL,
    score           INT             NOT NULL DEFAULT 0,
    memo            VARCHAR(255)    NULL,
    created_by      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT game_score_logs_subject_type_check CHECK (subject_type IN ('team', 'user')),
    CONSTRAINT fk_game_score_logs_session    FOREIGN KEY (session_id) REFERENCES game_sessions (id),
    CONSTRAINT fk_game_score_logs_chat_log   FOREIGN KEY (chat_log_id) REFERENCES game_chat_logs (id),
    CONSTRAINT fk_game_score_logs_created_by FOREIGN KEY (created_by) REFERENCES users (id),
    CONSTRAINT fk_game_score_logs_updated_by FOREIGN KEY (updated_by) REFERENCES users (id),
    CONSTRAINT uq_game_score_logs_chat_log_id UNIQUE (chat_log_id)
);

-- ------------------------------------------------------------
-- game_results
-- ------------------------------------------------------------
CREATE TABLE game_results (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NOT NULL,
    subject_type    VARCHAR(10)     NOT NULL,
    subject_id      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT game_results_subject_type_check CHECK (subject_type IN ('team', 'user')),
    CONSTRAINT fk_game_results_session FOREIGN KEY (session_id) REFERENCES game_sessions (id)
);

-- ------------------------------------------------------------
-- game_chat_logs  (round_id 컬럼 추가됨)
-- ------------------------------------------------------------
CREATE TABLE game_chat_logs (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NOT NULL,
    round_id        INT             NULL,
    user_id         INT             NOT NULL,
    message         VARCHAR(255)    NOT NULL,
    is_correct      BOOLEAN         NOT NULL DEFAULT FALSE,
    server_time     TIMESTAMP       NOT NULL,
    CONSTRAINT fk_game_chat_logs_session FOREIGN KEY (session_id) REFERENCES game_sessions (id),
    CONSTRAINT fk_game_chat_logs_round   FOREIGN KEY (round_id)   REFERENCES game_rounds (id),
    CONSTRAINT fk_game_chat_logs_user    FOREIGN KEY (user_id)    REFERENCES users (id)
);

-- ------------------------------------------------------------
-- rewards  (season_id 추가됨 — 시즌별 도감)
-- ------------------------------------------------------------
CREATE TABLE rewards (
    id              SERIAL PRIMARY KEY,
    season_id       INT             NOT NULL,
    name            VARCHAR(100)    NOT NULL,
    description     TEXT            NULL,
    total_count     INT             NOT NULL,
    image_url       VARCHAR(255)    NULL,
    win_rate        FLOAT           NOT NULL DEFAULT 0.0,
    is_revealed     BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT fk_rewards_season  FOREIGN KEY (season_id)  REFERENCES seasons (id),
    CONSTRAINT fk_rewards_updated FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- reward_claims  (리워드 수령 이력)
-- ------------------------------------------------------------
CREATE TABLE reward_claims (
    id          SERIAL PRIMARY KEY,
    reward_id   INT         NOT NULL,
    user_id     INT         NOT NULL,
    claimed_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    created_by  INT         NOT NULL,
    CONSTRAINT uq_reward_claims_user       UNIQUE (reward_id, user_id),
    CONSTRAINT fk_reward_claims_reward     FOREIGN KEY (reward_id)  REFERENCES rewards (id),
    CONSTRAINT fk_reward_claims_user       FOREIGN KEY (user_id)    REFERENCES users (id),
    CONSTRAINT fk_reward_claims_created_by FOREIGN KEY (created_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- buff
-- ------------------------------------------------------------
CREATE TABLE buff (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    description     TEXT            NOT NULL,
    type            VARCHAR(10)     NOT NULL,
    effect_type     VARCHAR(20)     NOT NULL,
    duration        VARCHAR(20)     NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT buff_type_check        CHECK (type IN ('buff', 'debuff')),
    CONSTRAINT buff_effect_type_check CHECK (effect_type IN ('point_penalty', 'point_freeze', 'action_restrict', 'steal', 'reroll', 'double', 'immunity', 'first_pick')),
    CONSTRAINT buff_duration_check    CHECK (duration IN ('instant', 'next_game', 'two_games', 'until_used')),
    CONSTRAINT fk_buff_updated FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- envelopes
-- ------------------------------------------------------------
CREATE TABLE envelopes (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NOT NULL,
    number          INT             NOT NULL,
    content_type    VARCHAR(10)     NOT NULL,
    reward_id       INT             NULL,
    buff_id         INT             NULL,
    owner_type      VARCHAR(10)     NULL,
    owner_id        INT             NULL,
    is_opened       BOOLEAN         NOT NULL DEFAULT FALSE,
    opened_at       TIMESTAMP       NULL,
    created_by      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT envelopes_content_type_check CHECK (content_type IN ('reward', 'blank')),
    CONSTRAINT envelopes_owner_type_check   CHECK (owner_type IN ('team', 'user')),
    CONSTRAINT fk_envelopes_session    FOREIGN KEY (session_id)  REFERENCES game_sessions (id),
    CONSTRAINT fk_envelopes_reward     FOREIGN KEY (reward_id)   REFERENCES rewards (id),
    CONSTRAINT fk_envelopes_buff       FOREIGN KEY (buff_id)     REFERENCES buff (id),
    CONSTRAINT fk_envelopes_created_by FOREIGN KEY (created_by)  REFERENCES users (id),
    CONSTRAINT fk_envelopes_updated_by FOREIGN KEY (updated_by)  REFERENCES users (id)
);

-- ------------------------------------------------------------
-- raffle_tickets
-- ------------------------------------------------------------
CREATE TABLE raffle_tickets (
    id              SERIAL PRIMARY KEY,
    session_id      INT             NULL,
    owner_type      VARCHAR(10)     NOT NULL,
    owner_id        INT             NOT NULL,
    action          VARCHAR(10)     NOT NULL,
    amount          INT             NOT NULL,
    reason          VARCHAR(255)    NULL,
    created_by      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT raffle_tickets_owner_type_check CHECK (owner_type IN ('team', 'user')),
    CONSTRAINT raffle_tickets_action_check     CHECK (action IN ('earned', 'used', 'lost')),
    CONSTRAINT fk_raffle_tickets_session    FOREIGN KEY (session_id) REFERENCES game_sessions (id),
    CONSTRAINT fk_raffle_tickets_created_by FOREIGN KEY (created_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- team_buffs
-- ------------------------------------------------------------
CREATE TABLE team_buffs (
    id              SERIAL PRIMARY KEY,
    team_id         INT             NOT NULL,
    buff_id         INT             NOT NULL,
    session_id      INT             NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    activated_at    TIMESTAMP       NULL,
    expires_after   INT             NULL,
    created_by      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT fk_team_buffs_team       FOREIGN KEY (team_id)       REFERENCES teams (id),
    CONSTRAINT fk_team_buffs_buff       FOREIGN KEY (buff_id)       REFERENCES buff (id),
    CONSTRAINT fk_team_buffs_session    FOREIGN KEY (session_id)    REFERENCES game_sessions (id),
    CONSTRAINT fk_team_buffs_expires    FOREIGN KEY (expires_after) REFERENCES game_sessions (id),
    CONSTRAINT fk_team_buffs_created_by FOREIGN KEY (created_by)    REFERENCES users (id),
    CONSTRAINT fk_team_buffs_updated_by FOREIGN KEY (updated_by)    REFERENCES users (id)
);

-- ------------------------------------------------------------
-- hidden_roles
-- ------------------------------------------------------------
CREATE TABLE hidden_roles (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100)    NOT NULL,
    description         TEXT            NOT NULL,
    scope               VARCHAR(10)     NOT NULL,
    success_condition   TEXT            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP       NULL,
    updated_by          INT             NULL,
    CONSTRAINT hidden_roles_scope_check CHECK (scope IN ('team', 'global')),
    CONSTRAINT fk_hidden_roles_updated  FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- user_hidden_roles
-- ------------------------------------------------------------
CREATE TABLE user_hidden_roles (
    id              SERIAL PRIMARY KEY,
    season_id       INT             NOT NULL,
    user_id         INT             NOT NULL,
    role_id         INT             NOT NULL,
    is_revealed     BOOLEAN         NOT NULL DEFAULT FALSE,
    is_success      BOOLEAN         NULL,
    judged_by       INT             NULL,
    judged_at       TIMESTAMP       NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT uq_user_hidden_roles_season_user UNIQUE (season_id, user_id),
    CONSTRAINT fk_user_hidden_roles_season    FOREIGN KEY (season_id)  REFERENCES seasons (id),
    CONSTRAINT fk_user_hidden_roles_user      FOREIGN KEY (user_id)    REFERENCES users (id),
    CONSTRAINT fk_user_hidden_roles_role      FOREIGN KEY (role_id)    REFERENCES hidden_roles (id),
    CONSTRAINT fk_user_hidden_roles_judged_by FOREIGN KEY (judged_by)  REFERENCES users (id),
    CONSTRAINT fk_user_hidden_roles_updated   FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- vote_items
-- ------------------------------------------------------------
CREATE TABLE vote_items (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    description     TEXT            NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT fk_vote_items_updated FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- vote_ballots
-- ------------------------------------------------------------
CREATE TABLE vote_ballots (
    id              SERIAL PRIMARY KEY,
    season_id       INT             NOT NULL,
    vote_item_id    INT             NOT NULL,
    status          VARCHAR(10)     NOT NULL DEFAULT 'waiting',
    order_index     INT             NOT NULL,
    opened_at       TIMESTAMP       NULL,
    closed_at       TIMESTAMP       NULL,
    created_by      INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT vote_ballots_status_check  CHECK (status IN ('waiting', 'open', 'closed')),
    CONSTRAINT fk_vote_ballots_season     FOREIGN KEY (season_id)    REFERENCES seasons (id),
    CONSTRAINT fk_vote_ballots_vote_item  FOREIGN KEY (vote_item_id) REFERENCES vote_items (id),
    CONSTRAINT fk_vote_ballots_created_by FOREIGN KEY (created_by)   REFERENCES users (id),
    CONSTRAINT fk_vote_ballots_updated_by FOREIGN KEY (updated_by)   REFERENCES users (id)
);

-- ------------------------------------------------------------
-- vote_records
-- ------------------------------------------------------------
CREATE TABLE vote_records (
    id              SERIAL PRIMARY KEY,
    ballot_id       INT             NOT NULL,
    voter_id        INT             NOT NULL,
    target_id       INT             NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vote_records_ballot_voter UNIQUE (ballot_id, voter_id),
    CONSTRAINT fk_vote_records_ballot FOREIGN KEY (ballot_id) REFERENCES vote_ballots (id),
    CONSTRAINT fk_vote_records_voter  FOREIGN KEY (voter_id)  REFERENCES users (id),
    CONSTRAINT fk_vote_records_target FOREIGN KEY (target_id) REFERENCES users (id)
);

-- ------------------------------------------------------------
-- speaking_events  (전역 발언권 이벤트 — count/speed/timing)
-- ------------------------------------------------------------
CREATE TABLE speaking_events (
    id          SERIAL PRIMARY KEY,
    season_id   INT             NOT NULL,
    mode        VARCHAR(10)     NOT NULL,
    status      VARCHAR(10)     NOT NULL DEFAULT 'open',
    duration    INT             NULL,
    target_time FLOAT           NULL,
    opened_at   TIMESTAMP       NOT NULL,
    closed_at   TIMESTAMP       NULL,
    signal_at   TIMESTAMP       NULL,
    created_by  INT             NOT NULL,
    updated_by  INT             NULL,
    updated_at  TIMESTAMP       NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT speaking_events_mode_check   CHECK (mode IN ('count', 'speed', 'timing')),
    CONSTRAINT speaking_events_status_check CHECK (status IN ('open', 'closed')),
    CONSTRAINT fk_speaking_events_season     FOREIGN KEY (season_id)  REFERENCES seasons (id),
    CONSTRAINT fk_speaking_events_created_by FOREIGN KEY (created_by) REFERENCES users (id),
    CONSTRAINT fk_speaking_events_updated_by FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- 시즌당 open 상태 이벤트는 1건만 허용 (부분 유니크 인덱스)
CREATE UNIQUE INDEX uq_speaking_events_one_open_per_season
    ON speaking_events (season_id)
    WHERE status = 'open';

-- ------------------------------------------------------------
-- speaking_submissions  (speed/timing 1인 1제출)
-- ------------------------------------------------------------
CREATE TABLE speaking_submissions (
    id          SERIAL PRIMARY KEY,
    event_id    INT             NOT NULL,
    user_id     INT             NOT NULL,
    value       FLOAT           NOT NULL,
    server_time TIMESTAMP       NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_speaking_submissions_event_user UNIQUE (event_id, user_id),
    CONSTRAINT fk_speaking_submissions_event FOREIGN KEY (event_id) REFERENCES speaking_events (id),
    CONSTRAINT fk_speaking_submissions_user  FOREIGN KEY (user_id)  REFERENCES users (id)
);

-- ------------------------------------------------------------
-- speaking_tap_logs  (count 모드 개별 탭 기록)
-- ------------------------------------------------------------
CREATE TABLE speaking_tap_logs (
    id          SERIAL PRIMARY KEY,
    event_id    INT             NOT NULL,
    user_id     INT             NOT NULL,
    server_time TIMESTAMP       NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_speaking_tap_logs_event FOREIGN KEY (event_id) REFERENCES speaking_events (id),
    CONSTRAINT fk_speaking_tap_logs_user  FOREIGN KEY (user_id)  REFERENCES users (id)
);

-- ------------------------------------------------------------
-- speaking_grants  (발언권 부여 기록)
-- ------------------------------------------------------------
CREATE TABLE speaking_grants (
    id          SERIAL PRIMARY KEY,
    event_id    INT             NOT NULL,
    user_id     INT             NOT NULL,
    rank        INT             NOT NULL,
    value       FLOAT           NOT NULL,
    granted_by  INT             NOT NULL,
    granted_at  TIMESTAMP       NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_speaking_grants_event_user UNIQUE (event_id, user_id),
    CONSTRAINT fk_speaking_grants_event      FOREIGN KEY (event_id)   REFERENCES speaking_events (id),
    CONSTRAINT fk_speaking_grants_user       FOREIGN KEY (user_id)    REFERENCES users (id),
    CONSTRAINT fk_speaking_grants_granted_by FOREIGN KEY (granted_by) REFERENCES users (id)
);

-- ============================================================
-- Column Comments
-- ============================================================

-- seasons
COMMENT ON COLUMN seasons.name       IS '시즌 이름 (예: 2026 가평 워크샵, 리허설)';
COMMENT ON COLUMN seasons.status     IS '시즌 상태 (preparing/active/done)';
COMMENT ON COLUMN seasons.started_at IS '시즌 시작 시각';
COMMENT ON COLUMN seasons.ended_at   IS '시즌 종료 시각';
COMMENT ON COLUMN seasons.del_yn     IS '소프트 삭제 여부';
COMMENT ON COLUMN seasons.created_by IS '시즌 생성한 운영자';
COMMENT ON COLUMN seasons.created_at IS '생성 시각';
COMMENT ON COLUMN seasons.updated_at IS '최종 수정 시각';
COMMENT ON COLUMN seasons.updated_by IS '최종 수정한 운영자';

-- users
COMMENT ON COLUMN users.username      IS '로그인 ID';
COMMENT ON COLUMN users.password      IS '비밀번호';
COMMENT ON COLUMN users.nickname      IS '화면 표시 이름';
COMMENT ON COLUMN users.role          IS '권한 (admin/user)';
COMMENT ON COLUMN users.point         IS '개인 누적 포인트';
COMMENT ON COLUMN users.profile_image IS '프로필 이미지 URL';
COMMENT ON COLUMN users.created_at    IS '생성 시각';
COMMENT ON COLUMN users.updated_at    IS '최종 수정 시각';
COMMENT ON COLUMN users.updated_by    IS '최종 수정한 운영자';

-- teams
COMMENT ON COLUMN teams.season_id  IS '소속 시즌 ID';
COMMENT ON COLUMN teams.name       IS '팀 이름';
COMMENT ON COLUMN teams.del_yn     IS '소프트 삭제 여부';
COMMENT ON COLUMN teams.created_at IS '생성 시각';

-- team_members
COMMENT ON COLUMN team_members.season_id  IS '소속 시즌 ID';
COMMENT ON COLUMN team_members.team_id    IS '소속 팀 ID';
COMMENT ON COLUMN team_members.user_id    IS '유저 ID';
COMMENT ON COLUMN team_members.created_at IS '생성 시각';

-- game
COMMENT ON COLUMN game.title            IS '게임 이름 (예: 노래맞추기, 버튼 챌린지)';
COMMENT ON COLUMN game.description      IS '게임 설명 (툴팁 표시용)';
COMMENT ON COLUMN game.participant_type IS '참여 단위 (team_vs/individual/team_internal/representative)';
COMMENT ON COLUMN game.input_type       IS '참여 방식 (chat/button/offline/puzzle/vote/tap)';
COMMENT ON COLUMN game.created_at       IS '생성 시각';
COMMENT ON COLUMN game.updated_at       IS '최종 수정 시각';
COMMENT ON COLUMN game.updated_by       IS '최종 수정한 운영자';

-- timetable
COMMENT ON COLUMN timetable.season_id     IS '소속 시즌 ID';
COMMENT ON COLUMN timetable.game_id       IS '연결된 게임 ID';
COMMENT ON COLUMN timetable.phase         IS '진행 단계 구분 (예: 저녁식사 전, 저녁식사 후, 2일차)';
COMMENT ON COLUMN timetable.order_index   IS '전체 진행 순서';
COMMENT ON COLUMN timetable.label         IS '화면 표시용 라벨 (예: 에피타이저, 메인①)';
COMMENT ON COLUMN timetable.raffle_reward IS '라운드 종료 시 지급할 뽑기권 수';
COMMENT ON COLUMN timetable.created_at    IS '생성 시각';
COMMENT ON COLUMN timetable.updated_at    IS '최종 수정 시각';
COMMENT ON COLUMN timetable.updated_by    IS '최종 수정한 운영자';

-- game_sessions
COMMENT ON COLUMN game_sessions.timetable_id IS '연결된 타임테이블 항목 ID';
COMMENT ON COLUMN game_sessions.state        IS '게임 진행 상태 (idle/ready/in_progress/scoring/reward/done)';
COMMENT ON COLUMN game_sessions.seed         IS '룰렛/랜덤 결과 생성용 서버 시드값';
COMMENT ON COLUMN game_sessions.started_at   IS '게임 시작 시각';
COMMENT ON COLUMN game_sessions.ended_at     IS '게임 종료 시각';
COMMENT ON COLUMN game_sessions.created_at   IS '생성 시각';
COMMENT ON COLUMN game_sessions.updated_at   IS '최종 수정 시각';
COMMENT ON COLUMN game_sessions.updated_by   IS '상태 변경한 운영자';

-- game_rounds
COMMENT ON COLUMN game_rounds.session_id     IS '연결된 게임 세션 ID';
COMMENT ON COLUMN game_rounds.order_index    IS '세션 내 라운드 순서 (1..N)';
COMMENT ON COLUMN game_rounds.status         IS '라운드 상태 (waiting/open/closed)';
COMMENT ON COLUMN game_rounds.prompt         IS '문제/힌트 텍스트';
COMMENT ON COLUMN game_rounds.media_url      IS '문제용 미디어 URL (노래 파일 등)';
COMMENT ON COLUMN game_rounds.options        IS 'button 타입 보기 목록 (예: [''1번'',''2번'',''3번'',''4번''])';
COMMENT ON COLUMN game_rounds.correct_answer IS '정답 (공개 전 비노출)';
COMMENT ON COLUMN game_rounds.opened_at      IS '라운드 오픈 시각';
COMMENT ON COLUMN game_rounds.closed_at      IS '라운드 마감 시각';
COMMENT ON COLUMN game_rounds.tap_mode       IS 'tap 게임 모드 (count/speed/timing)';
COMMENT ON COLUMN game_rounds.duration       IS 'tap count 모드 타이머(초)';
COMMENT ON COLUMN game_rounds.target_time    IS 'tap timing 모드 목표 시간(초, 0.1 단위)';
COMMENT ON COLUMN game_rounds.signal_at      IS 'tap speed 모드 신호 발사 시각';
COMMENT ON COLUMN game_rounds.created_by     IS '라운드 생성한 운영자';
COMMENT ON COLUMN game_rounds.updated_by     IS '라운드 상태 변경한 운영자';
COMMENT ON COLUMN game_rounds.created_at     IS '생성 시각';
COMMENT ON COLUMN game_rounds.updated_at     IS '최종 수정 시각';

-- round_submissions
COMMENT ON COLUMN round_submissions.round_id    IS '연결된 라운드 ID';
COMMENT ON COLUMN round_submissions.user_id     IS '제출 유저 ID';
COMMENT ON COLUMN round_submissions.answer      IS '선택/제출한 답 (tap speed=반응ms, tap timing=경과초)';
COMMENT ON COLUMN round_submissions.is_correct  IS '정답 여부';
COMMENT ON COLUMN round_submissions.server_time IS '서버 수신 타임스탬프 (클라이언트 시간 무시)';
COMMENT ON COLUMN round_submissions.created_at  IS '생성 시각';

-- tap_logs
COMMENT ON COLUMN tap_logs.round_id    IS '연결된 라운드 ID';
COMMENT ON COLUMN tap_logs.user_id     IS '탭한 유저 ID';
COMMENT ON COLUMN tap_logs.server_time IS '서버 수신 타임스탬프';
COMMENT ON COLUMN tap_logs.created_at  IS '생성 시각';

-- game_score_logs
COMMENT ON COLUMN game_score_logs.session_id   IS '연결된 게임 세션 ID';
COMMENT ON COLUMN game_score_logs.subject_type IS '점수 단위 (team/user)';
COMMENT ON COLUMN game_score_logs.subject_id   IS 'subject_type에 따라 teams.id 또는 users.id';
COMMENT ON COLUMN game_score_logs.chat_log_id  IS '노래맞추기 정답 후보 채팅 로그 ID';
COMMENT ON COLUMN game_score_logs.score        IS '획득 점수';
COMMENT ON COLUMN game_score_logs.memo         IS '부가정보 (예: 수영 01:23, 자전거 02:45)';
COMMENT ON COLUMN game_score_logs.created_by   IS '점수 기입한 운영자';
COMMENT ON COLUMN game_score_logs.created_at   IS '생성 시각';
COMMENT ON COLUMN game_score_logs.updated_at   IS '최종 수정 시각';
COMMENT ON COLUMN game_score_logs.updated_by   IS '점수 수정한 운영자';

-- game_results
COMMENT ON COLUMN game_results.session_id   IS '연결된 게임 세션 ID';
COMMENT ON COLUMN game_results.subject_type IS '결과 단위 (team/user)';
COMMENT ON COLUMN game_results.subject_id   IS '최종 승자 팀/유저 ID';
COMMENT ON COLUMN game_results.created_at   IS '생성 시각';

-- game_chat_logs
COMMENT ON COLUMN game_chat_logs.session_id  IS '연결된 게임 세션 ID';
COMMENT ON COLUMN game_chat_logs.round_id    IS '연결된 라운드 ID (라운드제 채팅게임의 문제 단위)';
COMMENT ON COLUMN game_chat_logs.user_id     IS '채팅 입력 유저';
COMMENT ON COLUMN game_chat_logs.message     IS '입력 메시지';
COMMENT ON COLUMN game_chat_logs.is_correct  IS '정답 여부';
COMMENT ON COLUMN game_chat_logs.server_time IS '서버 수신 타임스탬프 (클라이언트 시간 무시)';

-- rewards
COMMENT ON COLUMN rewards.season_id   IS '소속 시즌 ID (시즌별 도감)';
COMMENT ON COLUMN rewards.name        IS '상품명 (예: 신세계 상품권 5만원)';
COMMENT ON COLUMN rewards.description IS '상품 설명';
COMMENT ON COLUMN rewards.total_count IS '총 수량';
COMMENT ON COLUMN rewards.image_url   IS '상품 이미지 URL (도감용)';
COMMENT ON COLUMN rewards.win_rate    IS '당첨 확률 (0.0~1.0). 관리자가 정수 퍼센트 입력 후 /100 저장.';
COMMENT ON COLUMN rewards.is_revealed IS '최초 당첨자 발생 시 true — 도감에 내용 공개';
COMMENT ON COLUMN rewards.created_at  IS '생성 시각';
COMMENT ON COLUMN rewards.updated_at  IS '최종 수정 시각';
COMMENT ON COLUMN rewards.updated_by  IS '최종 수정한 운영자';

-- reward_claims
COMMENT ON COLUMN reward_claims.reward_id   IS '수령한 리워드 ID';
COMMENT ON COLUMN reward_claims.user_id     IS '수령한 유저 ID';
COMMENT ON COLUMN reward_claims.claimed_at  IS '수령 처리 시각';
COMMENT ON COLUMN reward_claims.created_by  IS '기록한 운영자 ID';

-- buff
COMMENT ON COLUMN buff.name        IS '카드 이름 (예: 훈민정음, 왼손잡이)';
COMMENT ON COLUMN buff.description IS '카드 효과 설명';
COMMENT ON COLUMN buff.type        IS '버프/디버프 구분 (buff/debuff)';
COMMENT ON COLUMN buff.effect_type IS '효과 유형';
COMMENT ON COLUMN buff.duration    IS '지속 시간 (instant/next_game/two_games/until_used)';
COMMENT ON COLUMN buff.created_at  IS '생성 시각';
COMMENT ON COLUMN buff.updated_at  IS '최종 수정 시각';
COMMENT ON COLUMN buff.updated_by  IS '최종 수정한 운영자';

-- envelopes
COMMENT ON COLUMN envelopes.session_id   IS '발행된 게임 세션 ID';
COMMENT ON COLUMN envelopes.number       IS '봉투 번호';
COMMENT ON COLUMN envelopes.content_type IS '봉투 내용물 유형 (reward/blank)';
COMMENT ON COLUMN envelopes.reward_id    IS '내용물이 상품일 때 rewards.id';
COMMENT ON COLUMN envelopes.buff_id      IS '꽝 봉투에 동봉된 버프/디버프 카드 ID';
COMMENT ON COLUMN envelopes.owner_type   IS '봉투 소유 단위 (team/user)';
COMMENT ON COLUMN envelopes.owner_id     IS 'owner_type에 따라 teams.id 또는 users.id';
COMMENT ON COLUMN envelopes.is_opened    IS '개봉 여부';
COMMENT ON COLUMN envelopes.opened_at    IS '개봉 시각';
COMMENT ON COLUMN envelopes.created_by   IS '봉투 생성한 운영자';
COMMENT ON COLUMN envelopes.created_at   IS '생성 시각';
COMMENT ON COLUMN envelopes.updated_at   IS '최종 수정 시각';
COMMENT ON COLUMN envelopes.updated_by   IS '최종 수정한 운영자';

-- raffle_tickets
COMMENT ON COLUMN raffle_tickets.session_id IS '관련 게임 세션 ID (운영자 직접 부여 시 NULL)';
COMMENT ON COLUMN raffle_tickets.owner_type IS '뽑기권 소유 단위 (team/user)';
COMMENT ON COLUMN raffle_tickets.owner_id   IS 'owner_type에 따라 teams.id 또는 users.id';
COMMENT ON COLUMN raffle_tickets.action     IS '획득/사용/몰수 (earned/used/lost)';
COMMENT ON COLUMN raffle_tickets.amount     IS '변동 수량';
COMMENT ON COLUMN raffle_tickets.reason     IS '사유 (예: 게임보상, 도박승리, 운영자부여, 봉투뽑기)';
COMMENT ON COLUMN raffle_tickets.created_by IS '기록한 운영자 또는 시스템';
COMMENT ON COLUMN raffle_tickets.created_at IS '생성 시각';

-- team_buffs
COMMENT ON COLUMN team_buffs.team_id       IS '대상 팀 ID';
COMMENT ON COLUMN team_buffs.buff_id       IS '보유한 버프/디버프 ID';
COMMENT ON COLUMN team_buffs.session_id    IS '부여된 게임 세션 ID';
COMMENT ON COLUMN team_buffs.is_active     IS '현재 활성 여부';
COMMENT ON COLUMN team_buffs.activated_at  IS '실제 발동 시각';
COMMENT ON COLUMN team_buffs.expires_after IS '만료되는 게임 세션 ID';
COMMENT ON COLUMN team_buffs.created_by    IS '부여한 운영자';
COMMENT ON COLUMN team_buffs.created_at    IS '생성 시각';
COMMENT ON COLUMN team_buffs.updated_at    IS '최종 수정 시각';
COMMENT ON COLUMN team_buffs.updated_by    IS '최종 수정한 운영자';

-- hidden_roles
COMMENT ON COLUMN hidden_roles.name              IS '역할 이름 (예: 사대주의자, 바람잡이)';
COMMENT ON COLUMN hidden_roles.description       IS '역할 설명 및 미션 내용';
COMMENT ON COLUMN hidden_roles.scope             IS '역할 범위 (team/global)';
COMMENT ON COLUMN hidden_roles.success_condition IS '성공 판정 기준';
COMMENT ON COLUMN hidden_roles.created_at        IS '생성 시각';
COMMENT ON COLUMN hidden_roles.updated_at        IS '최종 수정 시각';
COMMENT ON COLUMN hidden_roles.updated_by        IS '최종 수정한 운영자';

-- user_hidden_roles
COMMENT ON COLUMN user_hidden_roles.season_id   IS '소속 시즌 ID';
COMMENT ON COLUMN user_hidden_roles.user_id     IS '역할 배분된 유저 ID';
COMMENT ON COLUMN user_hidden_roles.role_id     IS '배분된 역할 ID';
COMMENT ON COLUMN user_hidden_roles.is_revealed IS '공개 여부 (시상식 전까지 FALSE)';
COMMENT ON COLUMN user_hidden_roles.is_success  IS '미션 성공 여부 (NULL=미판정)';
COMMENT ON COLUMN user_hidden_roles.judged_by   IS '판정한 운영자';
COMMENT ON COLUMN user_hidden_roles.judged_at   IS '판정 시각';
COMMENT ON COLUMN user_hidden_roles.created_at  IS '배분 시각';
COMMENT ON COLUMN user_hidden_roles.updated_at  IS '최종 수정 시각';
COMMENT ON COLUMN user_hidden_roles.updated_by  IS '최종 수정한 운영자';

-- vote_items
COMMENT ON COLUMN vote_items.name        IS '투표 항목 이름 (예: MVP, MUVP, 트롤러)';
COMMENT ON COLUMN vote_items.description IS '투표 항목 설명';
COMMENT ON COLUMN vote_items.created_at  IS '생성 시각';
COMMENT ON COLUMN vote_items.updated_at  IS '최종 수정 시각';
COMMENT ON COLUMN vote_items.updated_by  IS '최종 수정한 운영자';

-- vote_ballots
COMMENT ON COLUMN vote_ballots.season_id    IS '소속 시즌 ID';
COMMENT ON COLUMN vote_ballots.vote_item_id IS '투표 항목 ID';
COMMENT ON COLUMN vote_ballots.status       IS '투표 상태 (waiting/open/closed)';
COMMENT ON COLUMN vote_ballots.order_index  IS '투표 진행 순서';
COMMENT ON COLUMN vote_ballots.opened_at    IS '투표 시작 시각';
COMMENT ON COLUMN vote_ballots.closed_at    IS '투표 종료 시각';
COMMENT ON COLUMN vote_ballots.created_by   IS '생성한 운영자';
COMMENT ON COLUMN vote_ballots.created_at   IS '생성 시각';
COMMENT ON COLUMN vote_ballots.updated_at   IS '최종 수정 시각';
COMMENT ON COLUMN vote_ballots.updated_by   IS '최종 수정한 운영자';

-- vote_records
COMMENT ON COLUMN vote_records.ballot_id  IS '연결된 투표지 ID';
COMMENT ON COLUMN vote_records.voter_id   IS '투표한 유저 ID';
COMMENT ON COLUMN vote_records.target_id  IS '투표 대상 유저 ID';
COMMENT ON COLUMN vote_records.created_at IS '생성 시각';

-- v5 신규 컬럼
COMMENT ON COLUMN seasons.gacha_pull_cost IS '뽑기 1회 차감 포인트';
COMMENT ON COLUMN timetable.main_visible  IS '메인 화면에서 이미지와 라벨을 강조 노출할지 여부';
COMMENT ON COLUMN timetable.score_mode    IS '스코어보드 집계 단위 오버라이드 (team/individual). NULL이면 게임 participant_type 사용';

-- speaking_events
COMMENT ON COLUMN speaking_events.season_id   IS '소속 시즌 ID';
COMMENT ON COLUMN speaking_events.mode        IS '발언권 이벤트 모드 (count/speed/timing)';
COMMENT ON COLUMN speaking_events.status      IS '이벤트 상태 (open/closed)';
COMMENT ON COLUMN speaking_events.duration    IS 'count 제한 시간';
COMMENT ON COLUMN speaking_events.target_time IS 'timing 목표 시간';
COMMENT ON COLUMN speaking_events.opened_at   IS '이벤트 시작 시각';
COMMENT ON COLUMN speaking_events.closed_at   IS '이벤트 마감 시각';
COMMENT ON COLUMN speaking_events.signal_at   IS 'speed 신호 시각';
COMMENT ON COLUMN speaking_events.created_by  IS '이벤트 생성 운영자';
COMMENT ON COLUMN speaking_events.updated_by  IS '이벤트 수정 운영자';

-- speaking_submissions
COMMENT ON COLUMN speaking_submissions.event_id    IS '연결된 발언권 이벤트 ID';
COMMENT ON COLUMN speaking_submissions.user_id     IS '제출 유저 ID';
COMMENT ON COLUMN speaking_submissions.value       IS '제출 기록';
COMMENT ON COLUMN speaking_submissions.server_time IS '서버 수신 시각';

-- speaking_tap_logs
COMMENT ON COLUMN speaking_tap_logs.event_id    IS '연결된 발언권 이벤트 ID';
COMMENT ON COLUMN speaking_tap_logs.user_id     IS '탭한 유저 ID';
COMMENT ON COLUMN speaking_tap_logs.server_time IS '서버 수신 시각';

-- speaking_grants
COMMENT ON COLUMN speaking_grants.event_id   IS '연결된 발언권 이벤트 ID';
COMMENT ON COLUMN speaking_grants.user_id    IS '발언권을 받은 유저 ID';
COMMENT ON COLUMN speaking_grants.rank       IS '결과 순위';
COMMENT ON COLUMN speaking_grants.value      IS '결과 기록';
COMMENT ON COLUMN speaking_grants.granted_by IS '발언권 부여 운영자';
COMMENT ON COLUMN speaking_grants.granted_at IS '발언권 부여 시각';
