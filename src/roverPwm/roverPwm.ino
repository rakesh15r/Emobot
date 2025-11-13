#include <ArduinoJson.h>

//#######################################
// Pin mappings for Arduino UNO
//#######################################

// ---------- Left Motor ----------
int m1_EL_Start_Stop = 8;   // EL (digital enable)
int m1_Signal_hall   = 2;   // Hall sensor input (interrupt-capable)
int m1_ZF_Direction  = 7;   // ZF (direction)
int m1_VR_speed      = 9;   // VR (PWM output)

// ---------- Right Motor ----------
int m2_EL_Start_Stop = 5;   // EL (digital enable)
int m2_Signal_hall   = 3;   // Hall sensor input
int m2_ZF_Direction  = 4;   // ZF (direction)
int m2_VR_speed      = 10;  // VR (PWM output)

//#######################################
// Variables
//#######################################
volatile int left_pos = 0;
volatile int right_pos = 0;

int left_steps = 0;
int right_steps = 0;

int left_speed = 0;
int right_speed = 0;

String left_direction = "stop";
String right_direction = "stop";

//#######################################
// ISRs for Hall sensors
//#######################################
void leftPlus() {
  left_pos++;
  if (left_pos >= left_steps) {
    wheelStopLeft();
    left_pos = 0;
  }
}
/*
{
            "left":  {"direction": "forward", "steps": 2000, "speed": 20},
            "right": {"direction": "forward", "steps": 2000, "speed": 20}
        }
*/

void rightPlus() {
  right_pos++;
  if (right_pos >= right_steps) {
    wheelStopRight();
    right_pos = 0;
  }
}

//#######################################
// Setup
//#######################################
void setup() {
  Serial.begin(115200);

  // Left motor setup
  pinMode(m1_EL_Start_Stop, OUTPUT);
  pinMode(m1_Signal_hall, INPUT);
  pinMode(m1_ZF_Direction, OUTPUT);
  pinMode(m1_VR_speed, OUTPUT);

  // Right motor setup
  pinMode(m2_EL_Start_Stop, OUTPUT);
  pinMode(m2_Signal_hall, INPUT);
  pinMode(m2_ZF_Direction, OUTPUT);
  pinMode(m2_VR_speed, OUTPUT);

  // Disable both motors initially
  digitalWrite(m1_EL_Start_Stop, LOW);
  digitalWrite(m2_EL_Start_Stop, LOW);
  analogWrite(m1_VR_speed, 0);
  analogWrite(m2_VR_speed, 0);

  // Attach interrupts for hall sensors
  attachInterrupt(digitalPinToInterrupt(m1_Signal_hall), leftPlus, CHANGE);
  attachInterrupt(digitalPinToInterrupt(m2_Signal_hall), rightPlus, CHANGE);

  Serial.println("System ready. Waiting for command...");
}

//#######################################
// Wheel control functions (UPDATED PWM LOGIC)
//#######################################

// ---------- LEFT ----------
void wheelStopLeft() {
  analogWrite(m1_VR_speed, 0);
  digitalWrite(m1_EL_Start_Stop, LOW);
}

void wheelMoveForwardLeft() {
  int pwm_val = constrain(abs(left_speed), 0, 255);

  digitalWrite(m1_ZF_Direction, HIGH);   // forward
  analogWrite(m1_VR_speed, pwm_val);
  digitalWrite(m1_EL_Start_Stop, HIGH);
}

void wheelMoveBackwardLeft() {
  int pwm_val = constrain(abs(left_speed), 0, 255);

  digitalWrite(m1_ZF_Direction, LOW);    // backward
  analogWrite(m1_VR_speed, pwm_val);
  digitalWrite(m1_EL_Start_Stop, HIGH);
}

// ---------- RIGHT ----------
void wheelStopRight() {
  analogWrite(m2_VR_speed, 0);
  digitalWrite(m2_EL_Start_Stop, LOW);
}

void wheelMoveForwardRight() {
  int pwm_val = constrain(abs(right_speed), 0, 255);

  digitalWrite(m2_ZF_Direction, LOW);    // forward (inverted)
  analogWrite(m2_VR_speed, pwm_val);
  digitalWrite(m2_EL_Start_Stop, HIGH);
}

void wheelMoveBackwardRight() {
  int pwm_val = constrain(abs(right_speed), 0, 255);

  digitalWrite(m2_ZF_Direction, HIGH);   // backward (inverted)
  analogWrite(m2_VR_speed, pwm_val);
  digitalWrite(m2_EL_Start_Stop, HIGH);
}

//#######################################
// Drive control
//#######################################
void driveLeft() {
  if (left_direction == "stop") {
    wheelStopLeft();
    return;
  }

  if (left_direction == "forward" && left_pos < left_steps)
    wheelMoveForwardLeft();
  else if (left_direction == "backward" && left_pos < left_steps)
    wheelMoveBackwardLeft();
  else {
    wheelStopLeft();
    left_pos = 0;
  }
}

void driveRight() {
  if (right_direction == "stop") {
    wheelStopRight();
    return;
  }

  if (right_direction == "forward" && right_pos < right_steps)
    wheelMoveForwardRight();
  else if (right_direction == "backward" && right_pos < right_steps)
    wheelMoveBackwardRight();
  else {
    wheelStopRight();
    right_pos = 0;
  }
}

//#######################################
// Main Loop
//#######################################
void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');

    StaticJsonDocument<400> doc;
    DeserializationError error = deserializeJson(doc, command);

    if (!error) {
      // Extract left wheel data
      left_direction = String((const char*)doc["left"]["direction"]);
      left_steps = doc["left"]["steps"] | 0;
      left_speed = doc["left"]["speed"] | 0;

      // Extract right wheel data
      right_direction = String((const char*)doc["right"]["direction"]);
      right_steps = doc["right"]["steps"] | 0;
      right_speed = doc["right"]["speed"] | 0;

      // Debug output
      Serial.println("=== LEFT WHEEL ===");
      Serial.print("Dir: "); Serial.println(left_direction);
      Serial.print("Steps: "); Serial.println(left_steps);
      Serial.print("Speed: "); Serial.println(left_speed);

      Serial.println("=== RIGHT WHEEL ===");
      Serial.print("Dir: "); Serial.println(right_direction);
      Serial.print("Steps: "); Serial.println(right_steps);
      Serial.print("Speed: "); Serial.println(right_speed);

      // Drive both
      driveLeft();
      driveRight();
    } else {
      Serial.println("JSON parse failed!");
    }
  }
}
