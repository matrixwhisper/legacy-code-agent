       IDENTIFICATION DIVISION.
       PROGRAM-ID. HOSPITAL01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO 'src/INPUT.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-INPUT-STATUS.
           SELECT OUTPUT-FILE ASSIGN TO 'record/OUTPUT.DAT'
                   ORGANIZATION IS LINE SEQUENTIAL
                   FILE STATUS IS WS-OUTPUT-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD INPUT-FILE.
       01 INPUT-REC-LINE           PIC X(100).
       FD OUTPUT-FILE.
       01 OUTPUT-REC               PIC X(80).
       WORKING-STORAGE SECTION.
       77 WS-INPUT-STATUS          PIC XX.
       77 WS-OUTPUT-STATUS         PIC XX.
       77 WS-EOF-FLAG              PIC X VALUE 'N'.
          88 WS-EOF                VALUE 'Y'.
          88 WS-NOT-EOF            VALUE 'N'.
       77 WS-ERROR-FLAG            PIC X VALUE 'N'.
          88 WS-ERROR              VALUE 'Y'.
          88 WS-NO-ERROR           VALUE 'N'.
       77 IR-PATIENT-ID            PIC X(10).
       77 IR-PATIENT-NAME          PIC X(30).
       77 IR-BASE-COST             PIC 9(8).
       77 IR-INSURANCE-TYPE        PIC X(3).
       77 IR-COVERAGE-LIMIT        PIC 9(8).
       77 IR-DAYS-STAYED           PIC 9(3).
       77 IR-ROOM-TYPE             PIC X(3).
       77 WS-ROOM-RATE             PIC 9(5)V9(2).
       77 WS-COVERAGE-RATE         PIC 9V9(2).
       77 WS-ROOM-CHARGE           PIC 9(8)V9(2).
       77 WS-PROCEDURE-COST        PIC 9(8)V9(2).
       77 WS-SUBTOTAL              PIC 9(8)V9(2).
       77 WS-SERVICE-FEE           PIC 9(8)V9(2).
       77 WS-TOTAL-BILL            PIC 9(8)V9(2).
       77 WS-INSURANCE-CALC        PIC 9(8)V9(2).
       77 WS-INSURANCE-PAYS        PIC 9(8)V9(2).
       77 WS-PATIENT-OWES          PIC 9(8)V9(2).
       01 WS-OUTPUT-REC            PIC X(80) VALUE SPACES.
       01 WS-DENY-REC.
          05 DR-PATIENT-ID         PIC X(10).
          05 DR-STATUS             PIC X(5).
          05 DR-REASON             PIC X(45).
          05 DR-FILLER             PIC X(20).
       01 WS-APPROVE-HDR.
          05 AH-PATIENT-ID         PIC X(10).
          05 AH-STATUS             PIC X(5).
          05 AH-FILLER             PIC X(65).
       01 WS-ITEM-REC.
          05 IT-LINE-NUM           PIC 9(2).
          05 FILLER                PIC X(1).
          05 IT-DESCRIPTION        PIC X(20).
          05 IT-AMOUNT-SIGN        PIC X(1).
          05 IT-AMOUNT-VALUE       PIC 9(8).99.
          05 IT-FILLER             PIC X(45).
       PROCEDURE DIVISION.
       MAIN-PROCEDURE.
           PERFORM OPEN-FILES THRU OPEN-FILES-EX
           IF WS-NO-ERROR
               PERFORM PROCESS-FILE THRU PROCESS-FILE-EX
                   UNTIL WS-EOF OR WS-ERROR
           END-IF
           PERFORM CLOSE-FILES THRU CLOSE-FILES-EX
           STOP RUN.
       OPEN-FILES.
           OPEN INPUT INPUT-FILE
           IF WS-INPUT-STATUS NOT = '00'
               MOVE 'Y' TO WS-ERROR-FLAG
           END-IF
           IF WS-NO-ERROR
               OPEN OUTPUT OUTPUT-FILE
               IF WS-OUTPUT-STATUS NOT = '00'
                   MOVE 'Y' TO WS-ERROR-FLAG
               END-IF
           END-IF
           IF WS-ERROR
               CONTINUE
           ELSE
               MOVE 'N' TO WS-EOF-FLAG
           END-IF.
       OPEN-FILES-EX.
           EXIT.
       PROCESS-FILE.
           READ INPUT-FILE
               AT END
                   MOVE 'Y' TO WS-EOF-FLAG
               NOT AT END
                   PERFORM PARSE-INPUT-LINE
                   PERFORM PROCESS-PATIENT THRU PROCESS-PATIENT-EX
           END-READ.
       PARSE-INPUT-LINE.
           UNSTRING INPUT-REC-LINE DELIMITED BY ';'
               INTO IR-PATIENT-ID
                    IR-PATIENT-NAME
                    IR-BASE-COST
                    IR-INSURANCE-TYPE
                    IR-COVERAGE-LIMIT
                    IR-DAYS-STAYED
                    IR-ROOM-TYPE
           END-UNSTRING.
       PROCESS-FILE-EX.
           EXIT.
       PROCESS-PATIENT.
           PERFORM DETERMINE-RATES THRU DETERMINE-RATES-EX
           PERFORM CALCULATE-BILL THRU CALCULATE-BILL-EX
           EVALUATE TRUE
               WHEN WS-PATIENT-OWES > 7500.00
                   PERFORM CREATE-DENIAL THRU CREATE-DENIAL-EX
               WHEN OTHER
                   PERFORM CREATE-APPROVAL THRU CREATE-APPROVAL-EX
           END-EVALUATE.
       PROCESS-PATIENT-EX.
           EXIT.
       DETERMINE-RATES.
           EVALUATE IR-ROOM-TYPE
               WHEN 'ICU'
                   MOVE 450.00 TO WS-ROOM-RATE
               WHEN 'REG'
                   MOVE 180.00 TO WS-ROOM-RATE
               WHEN OTHER
                   MOVE 180.00 TO WS-ROOM-RATE
           END-EVALUATE
           EVALUATE IR-INSURANCE-TYPE
               WHEN 'PRM'
                   MOVE 0.85 TO WS-COVERAGE-RATE
               WHEN 'STD'
                   MOVE 0.70 TO WS-COVERAGE-RATE
               WHEN 'BSC'
                   MOVE 0.50 TO WS-COVERAGE-RATE
               WHEN OTHER
                   MOVE 0.50 TO WS-COVERAGE-RATE
           END-EVALUATE.
       DETERMINE-RATES-EX.
           EXIT.
       CALCULATE-BILL.
           COMPUTE WS-ROOM-CHARGE ROUNDED =
               IR-DAYS-STAYED * WS-ROOM-RATE
           COMPUTE WS-PROCEDURE-COST ROUNDED =
               IR-BASE-COST * 1.23
           COMPUTE WS-SUBTOTAL ROUNDED =
               WS-ROOM-CHARGE + WS-PROCEDURE-COST
           COMPUTE WS-SERVICE-FEE ROUNDED =
               WS-SUBTOTAL * 0.065
           COMPUTE WS-TOTAL-BILL ROUNDED =
               WS-SUBTOTAL + WS-SERVICE-FEE
           COMPUTE WS-INSURANCE-CALC ROUNDED =
               WS-TOTAL-BILL * WS-COVERAGE-RATE
           IF WS-INSURANCE-CALC > IR-COVERAGE-LIMIT
               MOVE IR-COVERAGE-LIMIT TO WS-INSURANCE-PAYS
           ELSE
               MOVE WS-INSURANCE-CALC TO WS-INSURANCE-PAYS
           END-IF
           COMPUTE WS-PATIENT-OWES ROUNDED =
               WS-TOTAL-BILL - WS-INSURANCE-PAYS.
       CALCULATE-BILL-EX.
           EXIT.
       CREATE-DENIAL.
           MOVE IR-PATIENT-ID TO DR-PATIENT-ID
           MOVE 'DENY ' TO DR-STATUS
           MOVE 'PATIENT LIABILITY EXCEEDS MAXIMUM THRESHOLD'
               TO DR-REASON
           MOVE SPACES TO DR-FILLER
           MOVE WS-DENY-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC
           IF WS-OUTPUT-STATUS NOT = '00'
               MOVE 'Y' TO WS-ERROR-FLAG
           END-IF.
       CREATE-DENIAL-EX.
           EXIT.
       CREATE-APPROVAL.
           MOVE IR-PATIENT-ID TO AH-PATIENT-ID
           MOVE 'APPRO' TO AH-STATUS
           MOVE SPACES TO AH-FILLER
           MOVE WS-APPROVE-HDR TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC
           IF WS-OUTPUT-STATUS NOT = '00'
               MOVE 'Y' TO WS-ERROR-FLAG
           END-IF
           PERFORM WRITE-ITEM-ROOM THRU WRITE-ITEM-ROOM-EX
           PERFORM WRITE-ITEM-PROC THRU WRITE-ITEM-PROC-EX
           PERFORM WRITE-ITEM-FEE THRU WRITE-ITEM-FEE-EX
           PERFORM WRITE-ITEM-INS THRU WRITE-ITEM-INS-EX
           PERFORM WRITE-ITEM-OWES THRU WRITE-ITEM-OWES-EX.
       CREATE-APPROVAL-EX.
           EXIT.
       WRITE-ITEM-ROOM.
           MOVE 01 TO IT-LINE-NUM
           MOVE 'ROOM CHARGES        ' TO IT-DESCRIPTION
           MOVE ' ' TO IT-AMOUNT-SIGN
           MOVE WS-ROOM-CHARGE TO IT-AMOUNT-VALUE
           MOVE SPACES TO IT-FILLER
           MOVE WS-ITEM-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC.
       WRITE-ITEM-ROOM-EX.
           EXIT.
       WRITE-ITEM-PROC.
           MOVE 02 TO IT-LINE-NUM
           MOVE 'PROCEDURE COST      ' TO IT-DESCRIPTION
           MOVE ' ' TO IT-AMOUNT-SIGN
           MOVE WS-PROCEDURE-COST TO IT-AMOUNT-VALUE
           MOVE SPACES TO IT-FILLER
           MOVE WS-ITEM-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC.
       WRITE-ITEM-PROC-EX.
           EXIT.
       WRITE-ITEM-FEE.
           MOVE 03 TO IT-LINE-NUM
           MOVE 'SERVICE FEE         ' TO IT-DESCRIPTION
           MOVE ' ' TO IT-AMOUNT-SIGN
           MOVE WS-SERVICE-FEE TO IT-AMOUNT-VALUE
           MOVE SPACES TO IT-FILLER
           MOVE WS-ITEM-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC.
       WRITE-ITEM-FEE-EX.
           EXIT.
       WRITE-ITEM-INS.
           MOVE 04 TO IT-LINE-NUM
           MOVE 'INSURANCE PAID      ' TO IT-DESCRIPTION
           MOVE '-' TO IT-AMOUNT-SIGN
           MOVE WS-INSURANCE-PAYS TO IT-AMOUNT-VALUE
           MOVE SPACES TO IT-FILLER
           MOVE WS-ITEM-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC.
       WRITE-ITEM-INS-EX.
           EXIT.
       WRITE-ITEM-OWES.
           MOVE 05 TO IT-LINE-NUM
           MOVE 'PATIENT OWES        ' TO IT-DESCRIPTION
           MOVE ' ' TO IT-AMOUNT-SIGN
           MOVE WS-PATIENT-OWES TO IT-AMOUNT-VALUE
           MOVE SPACES TO IT-FILLER
           MOVE WS-ITEM-REC TO WS-OUTPUT-REC
           WRITE OUTPUT-REC FROM WS-OUTPUT-REC.
       WRITE-ITEM-OWES-EX.
           EXIT.
       CLOSE-FILES.
           IF WS-INPUT-STATUS = '00' OR '10'
               CLOSE INPUT-FILE
           END-IF
           IF WS-OUTPUT-STATUS = '00' OR '10'
               CLOSE OUTPUT-FILE
           END-IF.
       CLOSE-FILES-EX.
           EXIT.