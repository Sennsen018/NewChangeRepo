-- PostgreSQL Schema for Attendeez

-- 1. Admins Table
CREATE TABLE IF NOT EXISTS Admins (
    admin_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL
);

-- 2. Teachers Table
CREATE TABLE IF NOT EXISTS Teachers (
    uTID VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Archived')),
    failed_attempts INT DEFAULT 0,
    lockout_time TIMESTAMP NULL
);

-- 3. Students Table
CREATE TABLE IF NOT EXISTS Students (
    uSID VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    course VARCHAR(100),
    level VARCHAR(20),
    section VARCHAR(50),
    status VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Archived')),
    failed_attempts INT DEFAULT 0,
    lockout_time TIMESTAMP NULL
);

-- 4. Subjects Table
CREATE TABLE IF NOT EXISTS Subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_code VARCHAR(20) UNIQUE NOT NULL,
    subject_name VARCHAR(100) NOT NULL
);

-- 5. Teacher Assignments Table
CREATE TABLE IF NOT EXISTS Teacher_Assignments (
    assignment_id SERIAL PRIMARY KEY,
    uTID VARCHAR(20),
    subject_id INT,
    section VARCHAR(50),
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id) ON DELETE CASCADE
);

-- 6. Enrollments Table
CREATE TABLE IF NOT EXISTS Enrollments (
    enrollment_id SERIAL PRIMARY KEY,
    uSID VARCHAR(20),
    subject_id INT,
    section VARCHAR(50),
    FOREIGN KEY (uSID) REFERENCES Students(uSID) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id) ON DELETE CASCADE
);

-- 7. Schedule Table
CREATE TABLE IF NOT EXISTS schedule (
    schedule_id SERIAL PRIMARY KEY,
    subject_id INT,
    uTID VARCHAR(20),
    section VARCHAR(50),
    day_of_week VARCHAR(20),
    start_time TIME,
    end_time TIME,
    room VARCHAR(50),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id) ON DELETE CASCADE,
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID) ON DELETE CASCADE
);

-- 8. Sessions Table
CREATE TABLE IF NOT EXISTS Sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    uTID VARCHAR(20),
    subject_id INT,
    section VARCHAR(50),
    random_token VARCHAR(50) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    status VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Ended')),
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

-- 9. Attendance Table
CREATE TABLE IF NOT EXISTS Attendance (
    attendance_id SERIAL PRIMARY KEY,
    session_id VARCHAR(50),
    uSID VARCHAR(20),
    scan_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'Present' CHECK (status IN ('Present', 'Absent', 'Late', 'Flagged')),
    remarks VARCHAR(255),
    is_valid VARCHAR(10) DEFAULT 'Valid' CHECK (is_valid IN ('Valid', 'Invalid')),
    student_lat DECIMAL(10, 8),
    student_lon DECIMAL(11, 8),
    distance_meters DECIMAL(10, 2),
    behavior_flags TEXT,
    FOREIGN KEY (session_id) REFERENCES Sessions(session_id),
    FOREIGN KEY (uSID) REFERENCES Students(uSID),
    UNIQUE (session_id, uSID)
);

-- 10. Attendance Audit Log Table
CREATE TABLE IF NOT EXISTS Attendance_Audit_Log (
    log_id SERIAL PRIMARY KEY,
    attendance_id INT,
    action VARCHAR(20) NOT NULL CHECK (action IN ('Update', 'Delete')),
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    changed_by_user_id VARCHAR(50) NOT NULL,
    changed_by_role VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. OTP Lockouts Table
CREATE TABLE IF NOT EXISTS otp_lockouts (
    email VARCHAR(100) PRIMARY KEY,
    lockout_until TIMESTAMP NOT NULL
);

-- 12. System Audit Log Table
CREATE TABLE IF NOT EXISTS System_Audit_Log (
    log_id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    entity_id VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('Create', 'Update', 'Delete')),
    performed_by_id VARCHAR(50) NOT NULL,
    performed_by_role VARCHAR(20) NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Notifications Table
CREATE TABLE IF NOT EXISTS Notifications (
    notification_id SERIAL PRIMARY KEY,
    uSID VARCHAR(20),
    message VARCHAR(255) NOT NULL,
    type VARCHAR(20) DEFAULT 'Info' CHECK (type IN ('Info', 'Warning', 'Alert')),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uSID) REFERENCES Students(uSID) ON DELETE CASCADE
);

-- 14. Submitted Reports Table
CREATE TABLE IF NOT EXISTS Submitted_Reports (
    report_id SERIAL PRIMARY KEY,
    uTID VARCHAR(20),
    subject_id INT,
    section VARCHAR(50),
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary_json TEXT,
    teacher_message TEXT,
    status VARCHAR(20) DEFAULT 'Submitted' CHECK (status IN ('Submitted', 'Reviewed')),
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

-- 15. Drop Requests Table
CREATE TABLE IF NOT EXISTS Drop_Requests (
    request_id SERIAL PRIMARY KEY,
    uTID VARCHAR(20),
    uSID VARCHAR(20),
    subject_id INT,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID),
    FOREIGN KEY (uSID) REFERENCES Students(uSID),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

-- 16. Excuse Letters Table
CREATE TABLE IF NOT EXISTS Excuse_Letters (
    letter_id SERIAL PRIMARY KEY,
    uSID VARCHAR(20),
    uTID VARCHAR(20),
    subject_id INT,
    message TEXT NOT NULL,
    file_path VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uSID) REFERENCES Students(uSID),
    FOREIGN KEY (uTID) REFERENCES Teachers(uTID),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

-- Sample Data
INSERT INTO Admins (username, password_hash, email) VALUES
('admin1', 'scrypt:32768:8:1$N82dGZp1t2rZ4B5y$4f10738eb2023d0611a21e428c9b98ff3c69c670ca7a1cbb612b7a0d4c82db7b4613fffc81e5932df8c42a2e6f47702f37c7689975765db805b53b817c763b65', 'admin@atendeez.com')
ON CONFLICT DO NOTHING;

INSERT INTO Subjects (subject_code, subject_name) VALUES
('IT101', 'Introduction to Computing'),
('IT102', 'Programming 1'),
('IT103', 'Database Management Systems')
ON CONFLICT DO NOTHING;
