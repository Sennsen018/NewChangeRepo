-- PostgreSQL Triggers for Attendeez System Flow

-- 1. Function: Notify student when a Drop Request is created or updated
CREATE OR REPLACE FUNCTION notify_on_drop_request()
RETURNS TRIGGER AS $$
DECLARE
    v_subject_name VARCHAR(100);
BEGIN
    SELECT subject_name INTO v_subject_name FROM Subjects WHERE subject_id = NEW.subject_id;
    
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO Notifications (uSID, message, type)
        VALUES (NEW.uSID, 'A drop request has been initiated for you in ' || v_subject_name, 'Warning');
    ELSIF (TG_OP = 'UPDATE' AND OLD.status != NEW.status) THEN
        INSERT INTO Notifications (uSID, message, type)
        VALUES (NEW.uSID, 'Your drop request status for ' || v_subject_name || ' has been updated to: ' || NEW.status, 
                CASE WHEN NEW.status = 'Approved' THEN 'Info' ELSE 'Alert' END);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Function: Notify student when an Excuse Letter status is updated
CREATE OR REPLACE FUNCTION notify_on_excuse_letter_status()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.status != NEW.status) THEN
        INSERT INTO Notifications (uSID, message, type)
        VALUES (NEW.uSID, 'Your excuse letter status has been updated to: ' || NEW.status, 
                CASE WHEN NEW.status = 'Approved' THEN 'Info' ELSE 'Alert' END);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Function: Notify student when attendance is recorded
CREATE OR REPLACE FUNCTION notify_on_attendance_recorded()
RETURNS TRIGGER AS $$
DECLARE
    v_subject_name VARCHAR(100);
BEGIN
    SELECT s.subject_name INTO v_subject_name 
    FROM Subjects s
    JOIN Sessions sess ON s.subject_id = sess.subject_id
    WHERE sess.session_id = NEW.session_id;

    IF (NEW.status = 'Present') THEN
        INSERT INTO Notifications (uSID, message, type)
        VALUES (NEW.uSID, 'Your attendance for today (' || to_char(CURRENT_DATE, 'MM-DD-YY') || ') has been successfully marked as Present.', 'Info');
    ELSIF (NEW.status = 'Flagged') THEN
        INSERT INTO Notifications (uSID, message, type)
        VALUES (NEW.uSID, 'Your attendance for today (' || to_char(CURRENT_DATE, 'MM-DD-YY') || ') has been flagged for review.', 'Alert');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Function: Auto-log attendance updates (Audit Log)
CREATE OR REPLACE FUNCTION log_attendance_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO Attendance_Audit_Log (attendance_id, action, old_status, new_status, changed_by_user_id, changed_by_role)
        VALUES (OLD.attendance_id, 'Update', OLD.status, NEW.status, 'SYSTEM_TRIGGER', 'System');
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO Attendance_Audit_Log (attendance_id, action, old_status, changed_by_user_id, changed_by_role)
        VALUES (OLD.attendance_id, 'Delete', OLD.status, 'SYSTEM_TRIGGER', 'System');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 5. Function: Prevent Duplicate Enrollments (Unique Subject & Unique Teacher per Student)
CREATE OR REPLACE FUNCTION prevent_duplicate_enrollments()
RETURNS TRIGGER AS $$
DECLARE
    v_subject_id INT;
    v_uTID VARCHAR(20);
    v_subject_name VARCHAR(100);
    v_teacher_name VARCHAR(150);
BEGIN
    -- Get details for the assignment we are trying to enroll in
    SELECT ta.subject_id, ta.uTID, s.subject_name, (t.first_name || ' ' || t.last_name) 
    INTO v_subject_id, v_uTID, v_subject_name, v_teacher_name
    FROM Teacher_Assignments ta
    JOIN Subjects s ON ta.subject_id = s.subject_id
    JOIN Teachers t ON ta.uTID = t.uTID
    WHERE ta.assignment_id = NEW.assignment_id;

    -- 1. Constraint: A student cannot be enrolled in the same subject twice (even with different teachers/sections)
    IF EXISTS (
        SELECT 1 FROM Enrollments e
        JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
        WHERE e.uSID = NEW.uSID AND ta.subject_id = v_subject_id
    ) THEN
        RAISE EXCEPTION 'Student is already enrolled in the subject "%". Duplicate subject enrollment is not allowed.', v_subject_name;
    END IF;

    -- 2. Constraint: A student must have a unique teacher (cannot have the same teacher for different subjects)
    IF EXISTS (
        SELECT 1 FROM Enrollments e
        JOIN Teacher_Assignments ta ON e.assignment_id = ta.assignment_id
        WHERE e.uSID = NEW.uSID AND ta.uTID = v_uTID
    ) THEN
        RAISE EXCEPTION 'Student is already handled by teacher %. Each subject must have a unique teacher for this student.', v_teacher_name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. Function: Notify student on excessive absences
CREATE OR REPLACE FUNCTION check_absences_limit()
RETURNS TRIGGER AS $$
DECLARE
    absence_count INT;
    v_subject_id INT;
    v_subject_name VARCHAR(100);
BEGIN
    -- Only check if the status is 'Absent'
    IF (NEW.status = 'Absent') THEN
        -- Get the subject_id from the session
        SELECT subject_id INTO v_subject_id FROM Sessions WHERE session_id = NEW.session_id;
        
        -- Get the subject_name
        SELECT subject_name INTO v_subject_name FROM Subjects WHERE subject_id = v_subject_id;
        
        -- Count absences for this student in this subject
        SELECT COUNT(*) INTO absence_count 
        FROM Attendance a
        JOIN Sessions s ON a.session_id = s.session_id
        WHERE a.uSID = NEW.uSID AND s.subject_id = v_subject_id AND a.status = 'Absent';
        
        -- Notify if absences exceed 3 (customizable limit)
        IF (absence_count >= 3) THEN
            INSERT INTO Notifications (uSID, message, type)
            VALUES (NEW.uSID, 'You have accumulated ' || absence_count || ' absences in ' || v_subject_name || '. Please contact your instructor.', 'Alert');
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- TRIGGERS --

-- Drop Request Notification Trigger
DROP TRIGGER IF EXISTS trg_notify_drop_request ON Drop_Requests;
CREATE TRIGGER trg_notify_drop_request
AFTER INSERT OR UPDATE ON Drop_Requests
FOR EACH ROW EXECUTE FUNCTION notify_on_drop_request();

-- Excuse Letter Notification Trigger
DROP TRIGGER IF EXISTS trg_notify_excuse_letter ON Excuse_Letters;
CREATE TRIGGER trg_notify_excuse_letter
AFTER UPDATE ON Excuse_Letters
FOR EACH ROW EXECUTE FUNCTION notify_on_excuse_letter_status();

-- Attendance Notification Trigger
DROP TRIGGER IF EXISTS trg_notify_attendance_recorded ON Attendance;
CREATE TRIGGER trg_notify_attendance_recorded
AFTER INSERT ON Attendance
FOR EACH ROW EXECUTE FUNCTION notify_on_attendance_recorded();

-- Attendance Audit Trigger
DROP TRIGGER IF EXISTS trg_log_attendance_changes ON Attendance;
CREATE TRIGGER trg_log_attendance_changes
AFTER UPDATE OR DELETE ON Attendance
FOR EACH ROW EXECUTE FUNCTION log_attendance_changes();

-- Duplicate Enrollment Prevention Trigger
DROP TRIGGER IF EXISTS trg_prevent_duplicate_enrollments ON Enrollments;
CREATE TRIGGER trg_prevent_duplicate_enrollments
BEFORE INSERT ON Enrollments
FOR EACH ROW EXECUTE FUNCTION prevent_duplicate_enrollments();

-- Absence Limit Notification Trigger
DROP TRIGGER IF EXISTS trg_check_absences_limit ON Attendance;
CREATE TRIGGER trg_check_absences_limit
AFTER INSERT OR UPDATE ON Attendance
FOR EACH ROW EXECUTE FUNCTION check_absences_limit();
