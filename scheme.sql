-- Create the database
CREATE DATABASE online_learning_platform;

-- Use the database
USE online_learning_platform;


-- Create users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('student', 'teacher') NOT NULL
);


-- Create courses table
CREATE TABLE courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    teacher_id INT,
    FOREIGN KEY (teacher_id) REFERENCES users(id)
);


-- Create course_files table
CREATE TABLE course_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT,
    file_path VARCHAR(255) NOT NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

-- Create students table
CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    performance JSON,
    engagement JSON,
    challenges JSON,
    support_needs JSON,
    level VARCHAR(50) DEFAULT 'Not Assessed',
    learning_style VARCHAR(50) DEFAULT '',
    personalized_insights TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);


-- Create enrollments table
CREATE TABLE enrollments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    student_name varchar(30) not NULL,
    course_id INT,
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    UNIQUE (student_id, course_id)
);



-- Create quizzes table
CREATE TABLE quizzes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    options JSON NOT NULL,
    correct_option INT NOT NULL,
    difficulty ENUM('Beginner', 'Intermediate', 'Advanced') NOT NULL
);


-- Create quiz_results table
CREATE TABLE quiz_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    score INT NOT NULL,
    level VARCHAR(50) NOT NULL,
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id)
);
-- Create course_ratings table
CREATE TABLE course_ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT,
    rating INT NOT NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);


-- Adding quiz_completed column to students table
ALTER TABLE students
ADD COLUMN quiz_completed BOOLEAN DEFAULT FALSE;


CREATE TABLE student_activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    activity_type ENUM('video', 'quiz', 'discussion', 'assignment', 'login') NOT NULL,
    activity_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_minutes INT DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE student_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    skill_score DECIMAL(5,2) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_skill (student_id, skill_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;