-- =====================================================
-- GYMHEART FITNESS - SUPABASE DATABASE SCHEMA
-- =====================================================
-- Hệ thống quản lý phòng gym với 3 loại người dùng:
-- 1. ADMIN: Quản lý toàn bộ hệ thống, khóa học, người dùng
-- 2. USER: Đăng ký khóa học, xem lịch tập
-- 3. COACH: Quản lý học viên, giáo án, lịch dạy
-- =====================================================

-- Drop existing tables (nếu có)
DROP TABLE IF EXISTS class_enrollments CASCADE;
DROP TABLE IF EXISTS lesson_plans CASCADE;
DROP TABLE IF EXISTS schedules CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;
DROP TYPE IF EXISTS enrollment_status CASCADE;
DROP TYPE IF EXISTS course_level CASCADE;
DROP TABLE IF EXISTS course_lessons CASCADE;
-- =====================================================
-- 1. ENUM TYPES
-- =====================================================

-- Loại người dùng
CREATE TYPE user_role AS ENUM ('admin', 'user', 'coach');

-- Trạng thái đăng ký khóa học
CREATE TYPE enrollment_status AS ENUM ('pending', 'active', 'completed', 'cancelled');

-- Cấp độ khóa học
CREATE TYPE course_level AS ENUM ('beginner', 'intermediate', 'advanced', 'all_levels');

-- =====================================================
-- 2. USERS TABLE - Bảng người dùng
-- =====================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    avatar_url TEXT,
    date_of_birth DATE,
    gender VARCHAR(10),
    address TEXT,
    role user_role NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    bio TEXT,
    specialization TEXT, -- Cho coach: chuyên môn
    years_of_experience INTEGER, -- Cho coach: số năm kinh nghiệm
    certification TEXT, -- Cho coach: chứng chỉ
    requested_role VARCHAR(20), -- Role xin cấp khi đăng ký (vd: 'coach'). Admin xét duyệt.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT chk_users_password_hash_bcrypt
            CHECK (password_hash ~ '^\$2[aby]\$[0-9]{2}\$.{53}$')
);

-- Index cho tìm kiếm nhanh
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- =====================================================
-- 3. COURSES TABLE - Bảng khóa học
-- =====================================================
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    duration_weeks INTEGER NOT NULL, -- Thời lượng khóa học (tuần)
    level course_level NOT NULL DEFAULT 'all_levels',
    max_students INTEGER DEFAULT 20,
    current_students INTEGER DEFAULT 0,
    image_url TEXT,
    coach_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    start_date DATE,
    end_date DATE,
    schedule_description TEXT, -- Mô tả lịch học
    benefits TEXT[], -- Lợi ích của khóa học (array)
    requirements TEXT[], -- Yêu cầu (array)
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_courses_coach_id ON courses(coach_id);
CREATE INDEX idx_courses_is_active ON courses(is_active);
CREATE INDEX idx_courses_level ON courses(level);

-- =====================================================
-- 4. CLASS_ENROLLMENTS TABLE - Bảng đăng ký khóa học
-- =====================================================
CREATE TABLE class_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    enrollment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status enrollment_status NOT NULL DEFAULT 'pending',
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, paid, refunded
    payment_method VARCHAR(50) DEFAULT 'cash', -- cash, transfer, card, ...
    payment_amount DECIMAL(10, 2),
    payment_date TIMESTAMP WITH TIME ZONE,
    progress_percentage INTEGER DEFAULT 0, -- Tiến độ hoàn thành (0-100%)
    notes TEXT,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id)
);

-- Index
CREATE INDEX idx_enrollments_user_id ON class_enrollments(user_id);
CREATE INDEX idx_enrollments_course_id ON class_enrollments(course_id);
CREATE INDEX idx_enrollments_status ON class_enrollments(status);

-- =====================================================
-- 5. SCHEDULES TABLE - Bảng lịch tập/dạy
-- =====================================================
CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    coach_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    day_of_week INTEGER NOT NULL, -- 0=Sunday, 1=Monday, ..., 6=Saturday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    location VARCHAR(255),
    room_number VARCHAR(50),
    max_capacity INTEGER DEFAULT 20,
    current_capacity INTEGER DEFAULT 0,
    is_recurring BOOLEAN DEFAULT true, -- Lặp lại hàng tuần
    specific_date DATE, -- Cho buổi học đặc biệt không lặp lại
    is_cancelled BOOLEAN DEFAULT false,
    cancellation_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_schedules_course_id ON schedules(course_id);
CREATE INDEX idx_schedules_coach_id ON schedules(coach_id);
CREATE INDEX idx_schedules_day_of_week ON schedules(day_of_week);

-- =====================================================
-- 6. LESSON_PLANS TABLE - Bảng giáo án
-- =====================================================
CREATE TABLE lesson_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    coach_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_number INTEGER NOT NULL,
    lesson_title VARCHAR(255) NOT NULL,
    objectives TEXT, -- Mục tiêu bài học
    warm_up TEXT, -- Khởi động
    main_exercises TEXT, -- Bài tập chính
    cool_down TEXT, -- Thư giãn
    equipment_needed TEXT[], -- Thiết bị cần thiết
    duration_minutes INTEGER,
    difficulty_level INTEGER, -- 1-5
    notes TEXT,
    video_url TEXT,
    is_published BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_lesson_plans_course_id ON lesson_plans(course_id);
CREATE INDEX idx_lesson_plans_coach_id ON lesson_plans(coach_id);

-- =====================================================
-- 7. COURSE_LESSONS TABLE - Lộ trình học từng khóa
-- =====================================================
CREATE TABLE IF NOT EXISTS course_lessons (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
    lesson_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    objectives TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_course_lessons_course_id ON course_lessons(course_id);
CREATE INDEX idx_course_lessons_order ON course_lessons(course_id, lesson_order);

-- Disable RLS (nhất quán với các bảng khác)
ALTER TABLE course_lessons DISABLE ROW LEVEL SECURITY;

-- =====================================================
-- 8. TRIGGER: Tự động cập nhật updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Áp dụng trigger cho tất cả các bảng
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_enrollments_updated_at BEFORE UPDATE ON class_enrollments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schedules_updated_at BEFORE UPDATE ON schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lesson_plans_updated_at BEFORE UPDATE ON lesson_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_course_lessons_updated_at BEFORE UPDATE ON course_lessons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 8. TRIGGER: Tự động cập nhật số lượng học viên
-- =====================================================
CREATE OR REPLACE FUNCTION update_course_student_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status = 'active' THEN
        UPDATE courses 
        SET current_students = current_students + 1 
        WHERE id = NEW.course_id;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status != 'active' AND NEW.status = 'active' THEN
            UPDATE courses 
            SET current_students = current_students + 1 
            WHERE id = NEW.course_id;
        ELSIF OLD.status = 'active' AND NEW.status != 'active' THEN
            UPDATE courses 
            SET current_students = current_students - 1 
            WHERE id = NEW.course_id;
        END IF;
    ELSIF TG_OP = 'DELETE' AND OLD.status = 'active' THEN
        UPDATE courses 
        SET current_students = current_students - 1 
        WHERE id = OLD.course_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_course_count_trigger
AFTER INSERT OR UPDATE OR DELETE ON class_enrollments
FOR EACH ROW EXECUTE FUNCTION update_course_student_count();

-- =====================================================
-- 9. ROW LEVEL SECURITY (RLS) - Bảo mật cấp hàng
-- =====================================================
-- LƯU Ý: Đang dùng CUSTOM AUTHENTICATION nên tạm DISABLE RLS
-- Nếu muốn bật RLS, cần chuyển sang dùng Supabase Auth

-- DISABLE RLS cho tất cả các bảng (cho phép truy cập tự do)
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE courses DISABLE ROW LEVEL SECURITY;
ALTER TABLE class_enrollments DISABLE ROW LEVEL SECURITY;
ALTER TABLE schedules DISABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_plans DISABLE ROW LEVEL SECURITY;

-- =====================================================
-- 10. SAMPLE DATA - Dữ liệu mẫu
-- =====================================================

-- Xóa dữ liệu cũ (nếu có)
DELETE FROM lesson_plans;
DELETE FROM schedules;
DELETE FROM class_enrollments;
DELETE FROM courses;
DELETE FROM users;

-- 10.1. Tạo 3 tài khoản mẫu
-- Password cho tất cả các tài khoản: "123456"
-- (Trong thực tế, nên hash bằng bcrypt hoặc tương tự)

-- ADMIN - Quản trị viên
INSERT INTO users (
    id, email, password_hash, full_name, phone, role, 
    is_active, bio, avatar_url, gender, date_of_birth
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'admin@gymheart.com',
    '$2a$10$rXqBzqE3LqJLVR0GyqBh5.vJKJLxPmXPxB5mWxYqJ6Zp5VcJ2ZxSq', -- 123456
    'admin',
    '0901234567',
    'admin',
    true,
    'Quản trị viên hệ thống GymHeart Fitness. Chịu trách nhiệm quản lý toàn bộ hoạt động của phòng gym.',
    'https://ui-avatars.com/api/?name=Admin&background=f42559&color=fff&size=200',
    'Nam',
    '1985-05-15'
);

-- COACH - Huấn luyện viên
INSERT INTO users (
    id, email, password_hash, full_name, phone, role,
    is_active, bio, specialization, years_of_experience, certification,
    avatar_url, gender, date_of_birth
) VALUES (
    '22222222-2222-2222-2222-222222222222',
    'coach@gymheart.com',
    '$2a$10$rXqBzqE3LqJLVR0GyqBh5.vJKJLxPmXPxB5mWxYqJ6Zp5VcJ2ZxSq', -- 123456
    'Trần Thị Nam',
    '0907654321',
    'coach',
    true,
    'Huấn luyện viên chuyên nghiệp với hơn 8 năm kinh nghiệm trong lĩnh vực fitness và bodybuilding.',
    'Fitness & Bodybuilding, Giảm cân',
    8,
    'ISSA Certified Personal Trainer, ACE Group Fitness Instructor',
    'https://ui-avatars.com/api/?name=Coach+Nam&background=f42559&color=fff&size=200',
    'Nữ',
    '1990-03-20'
);

-- USER - Học viên
INSERT INTO users (
    id, email, password_hash, full_name, phone, role,
    is_active, bio, avatar_url, gender, date_of_birth
) VALUES (
    '33333333-3333-3333-3333-333333333333',
    'user@gymheart.com',
    '$2a$10$rXqBzqE3LqJLVR0GyqBh5.vJKJLxPmXPxB5mWxYqJ6Zp5VcJ2ZxSq', -- 123456
    'Phạm Thị Lan Anh',
    '0912345678',
    'user',
    true,
    'Học viên nhiệt huyết của GymHeart, đang theo đuổi mục tiêu giảm cân và tăng cường sức khỏe.',
    'https://ui-avatars.com/api/?name=Lan+Anh&background=f42559&color=fff&size=200',
    'Nữ',
    '1995-08-10'
);

-- 10.2. Tạo khóa học mẫu

INSERT INTO courses (
    id, course_name, description, price, duration_weeks, level,
    max_students, current_students, coach_id, is_active, 
    start_date, end_date, schedule_description,
    benefits, requirements, created_by, image_url
) VALUES 
-- Khóa 1: Giảm cân thần tốc
(
    'c0000001-0000-0000-0000-000000000001',
    'Giảm Cân Thần Tốc 30 Ngày',
    'Chương trình giảm cân khoa học và hiệu quả, kết hợp giữa cardio và strength training. Phù hợp cho người muốn giảm 5-8kg trong 1 tháng.',
    2500000,
    4,
    'beginner',
    15,
    3,
    '22222222-2222-2222-2222-222222222222',
    true,
    '2026-02-10',
    '2026-03-10',
    'Thứ 2, 4, 6 - 6:00 AM - 7:30 AM',
    ARRAY['Giảm 5-8kg trong 30 ngày', 'Cải thiện sức khỏe tim mạch', 'Tăng cường thể lực', 'Tư vấn dinh dưỡng miễn phí'],
    ARRAY['Không có bệnh lý nặng', 'Cam kết tập luyện đầy đủ', 'Tuân thủ chế độ ăn'],
    '11111111-1111-1111-1111-111111111111',
    'https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=800'
),
-- Khóa 2: Tăng cơ bắp
(
    'c0000002-0000-0000-0000-000000000002',
    'Tăng Cơ Bắp Chuyên Nghiệp',
    'Lộ trình tập luyện tăng cơ chuyên nghiệp với các bài tập compound và isolation. Phù hợp cho người muốn phát triển cơ bắp toàn diện.',
    3500000,
    8,
    'intermediate',
    12,
    5,
    '22222222-2222-2222-2222-222222222222',
    true,
    '2026-02-15',
    '2026-04-15',
    'Thứ 3, 5, 7 - 5:30 PM - 7:00 PM',
    ARRAY['Tăng 3-5kg cơ nạc', 'Cải thiện sức mạnh tổng thể', 'Điêu khắc cơ thể', 'Hướng dẫn dinh dưỡng tăng cơ'],
    ARRAY['Có kinh nghiệm tập gym cơ bản', 'Không có chấn thương', 'Tuân thủ chế độ ăn tăng cơ'],
    '11111111-1111-1111-1111-111111111111',
    'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800'
),
-- Khóa 3: Yoga & Flexibility
(
    'c0000003-0000-0000-0000-000000000003',
    'Yoga Và Flexibility',
    'Khóa học Yoga kết hợp stretching giúp tăng cường sự linh hoạt, giảm stress và cải thiện tư thế. Phù hợp cho mọi lứa tuổi.',
    1800000,
    6,
    'all_levels',
    20,
    8,
    '22222222-2222-2222-2222-222222222222',
    true,
    '2026-02-12',
    '2026-03-26',
    'Thứ 2, 4, 6 - 7:00 PM - 8:00 PM',
    ARRAY['Tăng độ linh hoạt', 'Giảm căng thẳng', 'Cải thiện tư thế', 'Tăng cường thăng bằng'],
    ARRAY['Không cần kinh nghiệm', 'Mang theo thảm tập yoga'],
    '11111111-1111-1111-1111-111111111111',
    'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=800'
),
-- Khóa 4: HIIT Training
(
    'c0000004-0000-0000-0000-000000000004',
    'HIIT Training - Đốt Mỡ Cực Mạnh',
    'High Intensity Interval Training - Phương pháp tập luyện cường độ cao, đốt cháy mỡ thừa hiệu quả trong thời gian ngắn.',
    2800000,
    6,
    'intermediate',
    15,
    4,
    '22222222-2222-2222-2222-222222222222',
    true,
    '2026-02-17',
    '2026-03-31',
    'Thứ 3, 5 - 6:00 AM - 7:00 AM',
    ARRAY['Đốt cháy mỡ nhanh chóng', 'Tăng sức bền', 'Tiết kiệm thời gian', 'Tăng tốc độ trao đổi chất'],
    ARRAY['Sức khỏe tốt', 'Có thể lực cơ bản', 'Không có vấn đề về tim mạch'],
    '11111111-1111-1111-1111-111111111111',
    'https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=800'
),
-- Khóa 5: Boxing Fitness
(
    'c0000005-0000-0000-0000-000000000005',
    'Boxing Fitness - Võ Thuật & Thể Hình',
    'Kết hợp boxing và fitness training, giúp đốt cháy calories, tăng phản xạ và sức mạnh.',
    3000000,
    8,
    'beginner',
    12,
    2,
    '22222222-2222-2222-2222-222222222222',
    true,
    '2026-02-20',
    '2026-04-20',
    'Thứ 2, 4, 6 - 5:00 PM - 6:30 PM',
    ARRAY['Học kỹ thuật boxing cơ bản', 'Tăng cường thể lực', 'Đốt cháy 500-700 calories/buổi', 'Giải tỏa stress hiệu quả'],
    ARRAY['Không cần kinh nghiệm', 'Chuẩn bị găng tay boxing', 'Sức khỏe tốt'],
    '11111111-1111-1111-1111-111111111111',
    'https://images.unsplash.com/photo-1549719386-74dfcbf7dbed?w=800'
);

-- 10.3. Tạo đăng ký khóa học cho user

INSERT INTO class_enrollments (
    id, user_id, course_id, status, payment_status,
    payment_amount, payment_date, progress_percentage
) VALUES
-- User đăng ký khóa Giảm Cân
(
    '10000001-0000-0000-0000-000000000001',
    '33333333-3333-3333-3333-333333333333',
    'c0000001-0000-0000-0000-000000000001',
    'active',
    'paid',
    2500000,
    '2026-02-01 10:30:00',
    35
),
-- User đăng ký khóa Yoga
(
    '10000002-0000-0000-0000-000000000002',
    '33333333-3333-3333-3333-333333333333',
    'c0000003-0000-0000-0000-000000000003',
    'active',
    'paid',
    1800000,
    '2026-02-02 14:20:00',
    50
),
-- User đăng ký khóa HIIT (đang chờ)
(
    '10000003-0000-0000-0000-000000000003',
    '33333333-3333-3333-3333-333333333333',
    'c0000004-0000-0000-0000-000000000004',
    'pending',
    'pending',
    2800000,
    NULL,
    0
);

-- 10.4. Tạo lịch dạy

INSERT INTO schedules (
    id, course_id, coach_id, title, description,
    day_of_week, start_time, end_time, location, room_number, max_capacity
) VALUES
-- Lịch cho khóa Giảm Cân
(
    'a0000001-0000-0000-0000-000000000001',
    'c0000001-0000-0000-0000-000000000001',
    '22222222-2222-2222-2222-222222222222',
    'Giảm Cân - Thứ 2',
    'Cardio & HIIT Training',
    1, -- Monday
    '06:00:00',
    '07:30:00',
    'Phòng Cardio',
    'C101',
    15
),
(
    'a0000002-0000-0000-0000-000000000002',
    'c0000001-0000-0000-0000-000000000001',
    '22222222-2222-2222-2222-222222222222',
    'Giảm Cân - Thứ 4',
    'Strength Training',
    3, -- Wednesday
    '06:00:00',
    '07:30:00',
    'Phòng Cardio',
    'C101',
    15
),
-- Lịch cho khóa Tăng Cơ
(
    'a0000003-0000-0000-0000-000000000003',
    'c0000002-0000-0000-0000-000000000002',
    '22222222-2222-2222-2222-222222222222',
    'Tăng Cơ - Thứ 3',
    'Upper Body Workout',
    2, -- Tuesday
    '17:30:00',
    '19:00:00',
    'Phòng Tạ',
    'W201',
    12
),
-- Lịch cho khóa Yoga
(
    'a0000004-0000-0000-0000-000000000004',
    'c0000003-0000-0000-0000-000000000003',
    '22222222-2222-2222-2222-222222222222',
    'Yoga - Thứ 2',
    'Hatha Yoga & Stretching',
    1, -- Monday
    '19:00:00',
    '20:00:00',
    'Phòng Yoga',
    'Y301',
    20
);

-- 10.5. Tạo giáo án mẫu

INSERT INTO lesson_plans (
    id, course_id, coach_id, week_number, lesson_title,
    objectives, warm_up, main_exercises, cool_down,
    equipment_needed, duration_minutes, difficulty_level, is_published
) VALUES
-- Giáo án tuần 1 - Khóa Giảm Cân
(
    'b0000001-0000-0000-0000-000000000001',
    'c0000001-0000-0000-0000-000000000001',
    '22222222-2222-2222-2222-222222222222',
    1,
    'Tuần 1: Làm Quen Và Đánh Giá',
    'Đánh giá thể trạng ban đầu, làm quen với các bài tập cơ bản',
    '5 phút chạy bộ nhẹ + 5 phút stretching động',
    'Circuit Training: Squats 3x15, Push-ups 3x10, Jumping Jacks 3x20, Plank 3x30s',
    '10 phút stretching tĩnh + thở sâu',
    ARRAY['Thảm tập', 'Nước uống', 'Khăn'],
    75,
    2,
    true
),
-- Giáo án tuần 2 - Khóa Giảm Cân
(
    'b0000002-0000-0000-0000-000000000002',
    'c0000001-0000-0000-0000-000000000001',
    '22222222-2222-2222-2222-222222222222',
    2,
    'Tuần 2: Tăng Cường Cardio',
    'Tăng cường khả năng đốt cháy mỡ thông qua cardio',
    '5 phút chạy bộ + dynamic stretching',
    'HIIT: Sprint 30s/Rest 30s x 10 rounds, Burpees 3x12, Mountain Climbers 3x20',
    '10 phút cardio nhẹ + stretching',
    ARRAY['Giày chạy bộ', 'Thảm tập', 'Nước uống'],
    80,
    3,
    true
),
-- Giáo án tuần 1 - Khóa Tăng Cơ
(
    'b0000003-0000-0000-0000-000000000003',
    'c0000002-0000-0000-0000-000000000002',
    '22222222-2222-2222-2222-222222222222',
    1,
    'Tuần 1: Foundation - Upper Body',
    'Xây dựng nền tảng sức mạnh phần thân trên',
    '10 phút cardio nhẹ + shoulder mobility',
    'Bench Press 4x8, Barbell Row 4x8, Overhead Press 3x10, Chin-ups 3xMax',
    'Stretching thân trên + foam rolling',
    ARRAY['Barbell', 'Bench', 'Pull-up bar', 'Foam roller'],
    90,
    4,
    true
);

-- =====================================================
-- 11. VIEWS - Tạo views hữu ích
-- =====================================================

-- View: Thông tin chi tiết khóa học với coach
CREATE OR REPLACE VIEW v_course_details AS
SELECT 
    c.*,
    u.full_name as coach_name,
    u.email as coach_email,
    u.avatar_url as coach_avatar,
    u.specialization as coach_specialization,
    (c.max_students - c.current_students) as available_slots
FROM courses c
LEFT JOIN users u ON c.coach_id = u.id;

-- View: Thông tin chi tiết đăng ký khóa học
CREATE OR REPLACE VIEW v_enrollment_details AS
SELECT 
    e.*,
    u.full_name as student_name,
    u.email as student_email,
    u.avatar_url as student_avatar,
    c.course_name,
    c.duration_weeks,
    c.level as course_level,
    coach.full_name as coach_name
FROM class_enrollments e
JOIN users u ON e.user_id = u.id
JOIN courses c ON e.course_id = c.id
LEFT JOIN users coach ON c.coach_id = coach.id;

-- View: Lịch dạy chi tiết
CREATE OR REPLACE VIEW v_schedule_details AS
SELECT 
    s.*,
    c.course_name,
    c.level as course_level,
    u.full_name as coach_name,
    u.avatar_url as coach_avatar,
    CASE s.day_of_week
        WHEN 0 THEN 'Chủ Nhật'
        WHEN 1 THEN 'Thứ Hai'
        WHEN 2 THEN 'Thứ Ba'
        WHEN 3 THEN 'Thứ Tư'
        WHEN 4 THEN 'Thứ Năm'
        WHEN 5 THEN 'Thứ Sáu'
        WHEN 6 THEN 'Thứ Bảy'
    END as day_name
FROM schedules s
JOIN courses c ON s.course_id = c.id
JOIN users u ON s.coach_id = u.id;

-- =====================================================
-- 12. FUNCTIONS - Các hàm hữu ích
-- =====================================================

-- Hàm: Lấy danh sách học viên trong một khóa học
CREATE OR REPLACE FUNCTION get_course_students(course_uuid UUID)
RETURNS TABLE (
    student_id UUID,
    student_name VARCHAR,
    student_email VARCHAR,
    enrollment_date TIMESTAMP WITH TIME ZONE,
    progress_percentage INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.id,
        u.full_name,
        u.email,
        e.enrollment_date,
        e.progress_percentage
    FROM class_enrollments e
    JOIN users u ON e.user_id = u.id
    WHERE e.course_id = course_uuid 
      AND e.status = 'active'
    ORDER BY e.enrollment_date DESC;
END;
$$ LANGUAGE plpgsql;

-- Hàm: Lấy lịch dạy của coach trong tuần
CREATE OR REPLACE FUNCTION get_coach_weekly_schedule(coach_uuid UUID)
RETURNS TABLE (
    schedule_id UUID,
    course_name VARCHAR,
    day_of_week INTEGER,
    day_name VARCHAR,
    start_time TIME,
    end_time TIME,
    location VARCHAR,
    current_capacity INTEGER,
    max_capacity INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        c.course_name::VARCHAR,
        s.day_of_week,
        CASE s.day_of_week
            WHEN 0 THEN 'Chủ Nhật'::VARCHAR
            WHEN 1 THEN 'Thứ Hai'::VARCHAR
            WHEN 2 THEN 'Thứ Ba'::VARCHAR
            WHEN 3 THEN 'Thứ Tư'::VARCHAR
            WHEN 4 THEN 'Thứ Năm'::VARCHAR
            WHEN 5 THEN 'Thứ Sáu'::VARCHAR
            WHEN 6 THEN 'Thứ Bảy'::VARCHAR
        END,
        s.start_time,
        s.end_time,
        s.location::VARCHAR,
        s.current_capacity,
        s.max_capacity
    FROM schedules s
    JOIN courses c ON s.course_id = c.id
    WHERE s.coach_id = coach_uuid 
      AND s.is_cancelled = false
    ORDER BY s.day_of_week, s.start_time;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 13. FUNCTIONS: Admin quản trị
-- =====================================================

-- Hàm: Admin reset password của user bất kỳ
CREATE OR REPLACE FUNCTION admin_reset_user_password(
  target_user_id UUID,
  new_password TEXT
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result JSON;
BEGIN
  -- Kiểm tra user hiện tại có phải admin không
  IF NOT EXISTS (
    SELECT 1 FROM public.users 
    WHERE id = auth.uid() AND role = 'admin'
  ) THEN
    RAISE EXCEPTION 'Chỉ admin mới có quyền reset password';
  END IF;

  -- Cập nhật password
  UPDATE public.users
  SET password_hash = new_password, updated_at = NOW()
  WHERE id = target_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Không tìm thấy user';
  END IF;

  RETURN json_build_object('success', true, 'message', 'Password updated');
END;
$$;

-- =====================================================
-- HOÀN THÀNH DATABASE SETUP
-- =====================================================

-- Hiển thị thống kê
SELECT 'Database setup completed successfully!' as status;
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as total_courses FROM courses;
SELECT COUNT(*) as total_enrollments FROM class_enrollments;
SELECT COUNT(*) as total_schedules FROM schedules;
SELECT COUNT(*) as total_lesson_plans FROM lesson_plans;

-- 10.6. Tạo lộ trình học mẫu (course_lessons)
INSERT INTO course_lessons (course_id, lesson_order, title, content, objectives) VALUES
-- Khóa 1: Giảm Cân Thần Tốc
('c0000001-0000-0000-0000-000000000001', 1, 'Buổi 1: Khởi động và Đánh giá thể trạng', 'Làm quen với chương trình, đo chỉ số cơ thể (BMI, vòng eo), học khởi động an toàn.', 'Hiểu cơ chế giảm cân, nắm kỹ thuật khởi động đúng cách'),
('c0000001-0000-0000-0000-000000000001', 2, 'Buổi 2: Cardio cơ bản', 'Đi bộ nhanh, chạy nhẹ, đạp xe. Tập 30-40 phút với cường độ vừa phải.', 'Xây dựng nền tảng cardio, đốt 300-400 kcal'),
('c0000001-0000-0000-0000-000000000001', 3, 'Buổi 3: Circuit Training', 'Jumping jacks, burpees, mountain climbers. Mỗi động tác 30s, nghỉ 15s, 4-5 vòng.', 'Đốt calo tối đa 500-600 kcal, tăng trao đổi chất'),
('c0000001-0000-0000-0000-000000000001', 4, 'Buổi 4: Strength Training', 'Squat, lunge, push-up, plank với tạ nhỏ. 3 sets x 12-15 reps.', 'Tăng cơ nạc, nâng cao đốt calo khi nghỉ'),
('c0000001-0000-0000-0000-000000000001', 5, 'Buổi 5: HIIT nâng cao + Tổng kết', 'Sprint 30s + đi bộ 60s x 10 lần. Đo lại chỉ số, lên kế hoạch tiếp theo.', 'Đốt mỡ tối đa, đánh giá kết quả sau 30 ngày'),
-- Khóa 2: Tăng Cơ Bắp
('c0000002-0000-0000-0000-000000000002', 1, 'Buổi 1: Nền tảng - Upper Body', 'Bench Press, Barbell Row, Overhead Press, Chin-ups. Tập với tạ vừa sức.', 'Xây dựng sức mạnh thân trên'),
('c0000002-0000-0000-0000-000000000002', 2, 'Buổi 2: Nền tảng - Lower Body', 'Squat, Deadlift, Leg Press, Calf Raises. Đúng tư thế là ưu tiên.', 'Xây dựng sức mạnh thân dưới'),
('c0000002-0000-0000-0000-000000000002', 3, 'Buổi 3: Toàn thân + Dinh dưỡng', 'Compound exercises toàn thân, hướng dẫn chế độ ăn tăng cơ (protein, carb).', 'Phối hợp tập và ăn đúng cách để tăng cơ hiệu quả'),
-- Khóa 3: Yoga & Flexibility
('c0000003-0000-0000-0000-000000000003', 1, 'Buổi 1: Yoga cơ bản & Thở', 'Tư thế Mountain, Downward Dog, Child Pose. Hướng dẫn kỹ thuật thở.', 'Nắm tư thế nền tảng, xây dựng thói quen thở đúng'),
('c0000003-0000-0000-0000-000000000003', 2, 'Buổi 2: Tăng linh hoạt', 'Sun Salutation, Warrior series, hip opening poses. 60 phút liên tục.', 'Tăng độ linh hoạt toàn thân, giảm căng cơ');

SELECT COUNT(*) as total_course_lessons FROM course_lessons;

-- =====================================================
-- HƯỚNG DẪN SỬ DỤNG
-- =====================================================
/*
TÀI KHOẢN MẪU:
1. Admin: admin@gymheart.com / 123456
2. Coach: coach@gymheart.com / 123456
3. User: user@gymheart.com / 123456

CÁC BƯỚC CÀI ĐẶT TRÊN SUPABASE:
1. Đăng nhập vào Supabase Dashboard
2. Tạo project mới hoặc sử dụng project có sẵn
3. Vào SQL Editor
4. Copy toàn bộ nội dung file này và paste vào
5. Chạy query
6. Kiểm tra các bảng đã được tạo trong Table Editor

LƯU Ý:
- Password hash trong ví dụ này là giả định
- Trong production, sử dụng Supabase Auth để xử lý authentication
- Enable RLS policies theo nhu cầu bảo mật của bạn
- Cập nhật avatar_url với URL thực tế của ảnh
*/
