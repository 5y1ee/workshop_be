-- ============================================================
-- 가평 워크샵 웹 프로젝트 DDL (PostgreSQL)
-- ============================================================

-- ------------------------------------------------------------
-- seasons
-- ------------------------------------------------------------
CREATE TABLE seasons (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL,
    status      VARCHAR(20)     NOT NULL DEFAULT 'preparing',
    started_at  TIMESTAMP       NULL,
    ended_at    TIMESTAMP       NULL,
    created_by  INT             NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP       NULL,
    updated_by  INT             NULL,
    CONSTRAINT seasons_status_check CHECK (status IN ('preparing', 'active', 'done'))
);

-- ------------------------------------------------------------
-- users
-- ------------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50)     NOT NULL UNIQUE,
    password        VARCHAR(255)    NOT NULL,
    nickname        VARCHAR(50)     NOT NULL,
    role            VARCHAR(10)     NOT NULL,
    team_id         INT             NULL,
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
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_teams_season FOREIGN KEY (season_id) REFERENCES seasons (id)
);

-- ------------------------------------------------------------
-- 순환 참조 FK (users, seasons)
-- ------------------------------------------------------------
ALTER TABLE users
    ADD CONSTRAINT fk_users_team    FOREIGN KEY (team_id)    REFERENCES teams (id),
    ADD CONSTRAINT fk_users_updated FOREIGN KEY (updated_by) REFERENCES users (id);

ALTER TABLE seasons
    ADD CONSTRAINT fk_seasons_created FOREIGN KEY (created_by) REFERENCES users (id),
    ADD CONSTRAINT fk_seasons_updated FOREIGN KEY (updated_by) REFERENCES users (id);

-- ------------------------------------------------------------
-- game
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
    CONSTRAINT game_input_type_check       CHECK (input_type IN ('chat', 'button', 'offline', 'puzzle', 'vote')),
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
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
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
-- game_chat_logs
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
-- rewards
-- ------------------------------------------------------------
CREATE TABLE rewards (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    description     TEXT            NULL,
    total_count     INT             NOT NULL,
    image_url       VARCHAR(255)    NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NULL,
    updated_by      INT             NULL,
    CONSTRAINT fk_rewards_updated FOREIGN KEY (updated_by) REFERENCES users (id)
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

-- ============================================================
-- Column Comments
-- ============================================================

-- seasons
COMMENT ON COLUMN seasons.name       IS '시즌 이름 (예: 2026 가평 워크샵, 리허설)';
COMMENT ON COLUMN seasons.status     IS '시즌 상태 (preparing/active/done)';
COMMENT ON COLUMN seasons.started_at IS '시즌 시작 시각';
COMMENT ON COLUMN seasons.ended_at   IS '시즌 종료 시각';
COMMENT ON COLUMN seasons.created_by IS '시즌 생성한 운영자';
COMMENT ON COLUMN seasons.created_at IS '생성 시각';
COMMENT ON COLUMN seasons.updated_at IS '최종 수정 시각';
COMMENT ON COLUMN seasons.updated_by IS '최종 수정한 운영자';

-- users
COMMENT ON COLUMN users.username      IS '로그인 ID';
COMMENT ON COLUMN users.password      IS '비밀번호';
COMMENT ON COLUMN users.nickname      IS '화면 표시 이름';
COMMENT ON COLUMN users.role          IS '권한 (admin/user)';
COMMENT ON COLUMN users.team_id       IS '소속 팀 ID (팀 빌딩 전 NULL)';
COMMENT ON COLUMN users.point         IS '개인 누적 포인트';
COMMENT ON COLUMN users.profile_image IS '프로필 이미지 URL';
COMMENT ON COLUMN users.created_at    IS '생성 시각';
COMMENT ON COLUMN users.updated_at    IS '최종 수정 시각';
COMMENT ON COLUMN users.updated_by    IS '최종 수정한 운영자';

-- teams
COMMENT ON COLUMN teams.season_id  IS '소속 시즌 ID';
COMMENT ON COLUMN teams.name       IS '팀 이름';
COMMENT ON COLUMN teams.created_at IS '생성 시각';

-- game
COMMENT ON COLUMN game.title            IS '게임 이름 (예: 노래맞추기, 거짓말 탐지기)';
COMMENT ON COLUMN game.description      IS '게임 설명 (툴팁 표시용)';
COMMENT ON COLUMN game.participant_type IS '참여 단위 (team_vs/individual/team_internal/representative)';
COMMENT ON COLUMN game.input_type       IS '참여 방식 (chat/button/offline/puzzle/vote)';
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
COMMENT ON COLUMN rewards.name        IS '상품명 (예: 신세계 상품권 5만원)';
COMMENT ON COLUMN rewards.description IS '상품 설명';
COMMENT ON COLUMN rewards.total_count IS '총 수량';
COMMENT ON COLUMN rewards.image_url   IS '상품 이미지 URL (도감용)';
COMMENT ON COLUMN rewards.created_at  IS '생성 시각';
COMMENT ON COLUMN rewards.updated_at  IS '최종 수정 시각';
COMMENT ON COLUMN rewards.updated_by  IS '최종 수정한 운영자';

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
