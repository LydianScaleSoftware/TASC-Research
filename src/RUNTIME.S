****************************************
*
* RUNTIME
* THE LIBRARY OF THE TASC COMPILER, VERSION 2.01
* COPYRIGHT (C) 1981 MICROSOFT
*
* COMPILED PROGRAMS CALL THESE ROUTINES FOR ALMOST EVERY
* STATEMENT. IT LOADS AT $0803 BY DEFAULT ($0803-$17AF,
* 4013 BYTES).
*
****************************************
*
* PAGE ZERO, MEMORY AND ROM ADDRESSES
*
CHARAC   EQU  $0D                       ;TEMPORARY
ENDCHR   EQU  $0E                       ;TEMPORARY
NUMDIM   EQU  $0F                       ;TEMPORARY: DIMENSION COUNT
DIMFLG   EQU  $10                       ;TEMPORARY
DATFIRST EQU  $12                       ;HEADER: ADDRESS OF THE FIRST DATA ITEM (2 BYTES)
HIGHEST  EQU  $14                       ;HEADER: HIGHEST ADDRESS USED BY LIBRARY, PROGRAM OR VARIABLES (2)
HDRFLAG  EQU  $16                       ;HEADER: COMMON FLAG; ALSO A TEMPORARY
HGRSHAPE EQU  $1A                       ;HI-RES SHAPE POINTER (2)
CH       EQU  $24                       ;MONITOR: CURSOR COLUMN
H2       EQU  $2C                       ;MONITOR: RIGHT END OF A LO-RES LINE
V2       EQU  $2D                       ;MONITOR: BOTTOM END OF A LO-RES LINE
PROMPT   EQU  $33                       ;MONITOR: PROMPT CHARACTER
A1L      EQU  $3C                       ;MONITOR: A1 (2)
LINNUM   EQU  $50                       ;ADDRESS TEMPORARY (2)
TEMPPT   EQU  $52                       ;TEMPORARY
TPTR     EQU  $55                       ;TEMPORARY POINTER (2)
FLTVEC   EQU  $58                       ;JMP TO THE ROUTINE THAT FLOATS THE INTEGER ACCUMULATOR (3)
ERRVEC   EQU  $5B                       ;JMP TO THE CODE HANDLING ONERR (3)
RESULT   EQU  $62                       ;TEMPORARIES (5)
TXTTAB   EQU  $67                       ;APPLESOFT START OF PROGRAM (2)
COMBEG   EQU  $69                       ;START OF THE COMMON BLOCK - 1 (2)
NUMCEND  EQU  $6B                       ;END OF NUMERIC COMMON (2)
STRCEND  EQU  $6D                       ;END OF STRING COMMON (2)
FRETOP   EQU  $6F                       ;BOTTOM OF STRINGS - 1 (2)
INPOS    EQU  $71                       ;INPUT BUFFER POSITION ($FF NEW LINE, $FE USED UP)
MEMSIZ   EQU  $73                       ;HIMEM (2)
CURLIN   EQU  $75                       ;ADDRESS OF THE OBJECT CODE BEING EXECUTED (2)
STRACC   EQU  $77                       ;STRING ACCUMULATOR: THE LOADED STRING (2)
STRPSH   EQU  $79                       ;THE PUSHED STRING (2)
LOCBEG   EQU  $7B                       ;START OF LOCAL VARIABLES - 1 (2)
LOCNEND  EQU  $7D                       ;END OF LOCAL NUMERIC VARIABLES (2)
LOCSEND  EQU  $7F                       ;END OF LOCAL STRING VARIABLES (2)
VARNAM   EQU  $81                       ;TEMPORARY (2)
RETADR   EQU  $83                       ;TEMPORARY: A SAVED RETURN ADDRESS (2)
FORPNT   EQU  $85                       ;TEMPORARY POINTER (2)
TEMP3    EQU  $8A                       ;TEMPORARIES (5)
TEMP1    EQU  $93                       ;TEMPORARIES; ALSO THE COLLECTOR'S POINTERS (5)
FAC      EQU  $9D                       ;FLOATING POINT ACCUMULATOR (EXPONENT, 4 MANTISSA BYTES, SIGN AT $A2)
IARG     EQU  $9E                       ;INTEGER ARGUMENT (HIGH, LOW)
IACC     EQU  $A0                       ;INTEGER ACCUMULATOR (HIGH, LOW)
FACSIGN  EQU  $A2                       ;SIGN OF FAC
SERLEN   EQU  $A3                       ;TEMPORARY
ARG      EQU  $A5                       ;SECOND FLOATING POINT ACCUMULATOR (5, SIGN AT $AA)
ARGSIGN  EQU  $AA                       ;SIGN OF ARG
SGNCPR   EQU  $AB                       ;TEMPORARY: SIGN COMPARISON, NEGATION COUNT
SERPNT   EQU  $AD                       ;TEMPORARY (2)
FORPOP   EQU  $AF                       ;ADDRESS OF THE ROUTINE THAT POPS FOR ENTRIES (2)
CHRGET   EQU  $B1                       ;APPLESOFT CHRGET (MODIFIED)
CHRGOT   EQU  $B7                       ;CHRGOT, INSIDE CHRGET
TXTPTR   EQU  $B8                       ;TEXT POINTER, INSIDE CHRGET (2)
CHRPAT   EQU  $BA                       ;WHERE THE CHRGET PATCH GOES
ERRFLG   EQU  $D8                       ;$80 WHEN ONERR IS ACTIVE
ELTYPE   EQU  $D9                       ;TEMPORARY: ARRAY ELEMENT TYPE
ERRLIN   EQU  $DA                       ;OBJECT ADDRESS OF THE STATEMENT THAT FAILED (2)
ERRPOS   EQU  $DC                       ;TEMPORARY: ARRAY ELEMENT ADDRESS (2)
ERRSTK   EQU  $DF                       ;STACK POINTER BEFORE THE FAILED STATEMENT
HGRSCALE EQU  $E7                       ;HI-RES SCALE
SHAPETBL EQU  $E8                       ;ADDRESS OF THE SHAPE TABLE (2)
FIRST    EQU  $F0                       ;TEMPORARY: LO-RES / SHAPE ARGUMENT
SPEEDZ   EQU  $F1                       ;OUTPUT SPEED
TRCFLG   EQU  $F2                       ;TRACE FLAG
TXTPSV   EQU  $F4                       ;ONERR TEXT POINTER (2)
DATPTR   EQU  $F6                       ;POINTER INTO THE DATA ITEMS (2)
REMSTK   EQU  $F8                       ;STACK POINTER BEFORE THE STATEMENT
HGRROT   EQU  $F9                       ;HI-RES ROTATION
ZPFF     EQU  $FF                       ;LAST BYTE OF PAGE ZERO
STACK    EQU  $0100                     ;THE 6502 STACK
INBUF    EQU  $0200                     ;INPUT BUFFER
AMPER    EQU  $03F5                     ;AMPERSAND VECTOR (3)
ERROR    EQU  $D412                     ;ROM: REPORT ERROR X
INLIN    EQU  $D52C                     ;ROM: READ A LINE INTO THE INPUT BUFFER
INCHR    EQU  $D553                     ;ROM: READ A KEY
RUNCLR   EQU  $D566                     ;ROM: RUN, AFTER CLEARING VARIABLES
SCRTCH   EQU  $D64B                     ;ROM: NEW
STOPCC   EQU  $D863                     ;ROM: CONTROL-C BREAK
LET2     EQU  $DA65                     ;ROM: STORE FAC IN AN INTEGER VARIABLE (ROUND, RANGE CHECK)
CRDO     EQU  $DAFB                     ;ROM: PRINT A CARRIAGE RETURN
STROUT   EQU  $DB3A                     ;ROM: PRINT A STRING AT (Y,A)
OUTSP    EQU  $DB57                     ;ROM: PRINT A SPACE
OUTQUES  EQU  $DB5A                     ;ROM: PRINT A QUESTION MARK
OUTDO    EQU  $DB5C                     ;ROM: PRINT THE CHARACTER IN A
REENTER  EQU  $DB87                     ;ROM: ?REENTER (INSIDE INPERR)
SGNEXIT  EQU  $DE59                     ;ROM: SAVE THE SIGN COMPARISON, RETURN THE FAC EXPONENT (SETS THE FLAGS)
INTVAR   EQU  $DEE9                     ;ROM: LOAD THE INTEGER AT (VPNT) INTO FAC
AYINT    EQU  $E10C                     ;ROM: FAC TO A 16-BIT INTEGER IN FAC+3/FAC+4 ($A0/$A1)
GIVAYF   EQU  $E2F2                     ;ROM: FLOAT THE INTEGER (A HIGH, Y LOW) INTO FAC
CONINT2  EQU  $E6FE                     ;ROM: INSIDE CONINT: FAC+3/4 TO A BYTE IN X (0-255)
GETADR   EQU  $E752                     ;ROM: FAC TO A 16-BIT ADDRESS IN LINNUM
POKE2    EQU  $E77E                     ;ROM: INSIDE POKE: STORE X AT (LINNUM)
WAIT2    EQU  $E793                     ;ROM: INSIDE WAIT
FSUB     EQU  $E7A7                     ;ROM: FAC = (Y,A) - FAC
FADD     EQU  $E7BE                     ;ROM: FAC = (Y,A) + FAC
FADDT    EQU  $E7C1                     ;ROM: FAC = ARG + FAC
FMULT    EQU  $E97F                     ;ROM: FAC = (Y,A) * FAC
FMULTT   EQU  $E982                     ;ROM: FAC = ARG * FAC
CONUPK   EQU  $E9E3                     ;ROM: LOAD ARG FROM (Y,A)
FDIV     EQU  $EA66                     ;ROM: FAC = (Y,A) / FAC
FDIVT    EQU  $EA69                     ;ROM: FAC = ARG / FAC
MOVFM    EQU  $EAF9                     ;ROM: LOAD FAC FROM (Y,A)
MOV1F    EQU  $EB21                     ;ROM: PACK FAC INTO TEMP1
MOVMF    EQU  $EB2B                     ;ROM: STORE FAC, ROUNDED, AT (Y,X)
MOVFA    EQU  $EB53                     ;ROM: COPY ARG TO FAC
MOVAF    EQU  $EB63                     ;ROM: COPY FAC, ROUNDED, TO ARG
SIGN     EQU  $EB82                     ;ROM: SIGN OF FAC IN A
FLOAT    EQU  $EB93                     ;ROM: FLOAT THE SIGNED BYTE IN A
FCOMP    EQU  $EBB2                     ;ROM: COMPARE FAC WITH (Y,A): A = -1, 0 OR 1
FIN      EQU  $EC4A                     ;ROM: CONVERT THE NUMBER AT TXTPTR INTO FAC
INPRT    EQU  $ED19                     ;ROM: PRINT " IN " AND THE LINE NUMBER
PRNTFAC  EQU  $ED2E                     ;ROM: PRINT FAC
FOUT     EQU  $ED34                     ;ROM: CONVERT FAC TO A STRING AT $0100
NEGOP    EQU  $EED0                     ;ROM: FAC = -FAC
CHRGIMG  EQU  $F10B                     ;ROM: THE COPY OF CHRGET THAT INITIALIZES $B1-$C8
CHRCONT  EQU  $F114                     ;ROM: THE REST OF CHRGET AFTER THE SPACE CHECK
CALLROM  EQU  $F1D8                     ;ROM: INSIDE CALL: JSR (LINNUM)
INSLOT   EQU  $F1E1                     ;ROM: INSIDE IN#
PRSLOT   EQU  $F1E8                     ;ROM: INSIDE PR#
LINCHK   EQU  $F1FD                     ;ROM: LO-RES COORDINATE CHECK
PLOTCHK  EQU  $F220                     ;ROM: LO-RES COORDINATE CHECK (BELOW 48)
PLOT2    EQU  $F228                     ;ROM: INSIDE PLOT
HLIN2    EQU  $F235                     ;ROM: INSIDE HLIN
VLIN2    EQU  $F244                     ;ROM: INSIDE VLIN
COLOR2   EQU  $F252                     ;ROM: INSIDE COLOR=
VTAB2    EQU  $F259                     ;ROM: INSIDE VTAB
SPEED2   EQU  $F265                     ;ROM: INSIDE SPEED=
HPOSN    EQU  $F411                     ;ROM: POSITION THE HI-RES CURSOR
HPLOT0   EQU  $F457                     ;ROM: PLOT A HI-RES POINT
HGLIN    EQU  $F53A                     ;ROM: DRAW A HI-RES LINE
DRAW1    EQU  $F605                     ;ROM: DRAW A SHAPE
XDRAW1   EQU  $F661                     ;ROM: XDRAW A SHAPE
HCOLOR2  EQU  $F6EC                     ;ROM: INSIDE HCOLOR=
HTAB2    EQU  $F7EA                     ;ROM: INSIDE HTAB
MONSCRN  EQU  $F871                     ;ROM: MONITOR SCRN
PREAD    EQU  $FB1E                     ;ROM: READ A PADDLE
CROUT1   EQU  $FD8B                     ;ROM: CLEAR TO END OF LINE, CARRIAGE RETURN
*
         ORG  $0803                     ;THE LIBRARY'S USUAL ADDRESS
*
*--------------------------------------
* INIT: START A COMPILED PROGRAM. EVERY OBJECT FILE BEGINS WITH JSR
* INIT FOLLOWED BY A 17-BYTE HEADER: THE FIRST DATA ITEM, THE
* HIGHEST ADDRESS, THE COMMON BOUNDS (START-1, NUMERIC END, STRING
* END), THE LOCAL BOUNDS (THE SAME THREE), TWO BYTES EACH, AND THE
* COMMON FLAG (0 NONE OR DEFINE, $FF USE).
* INIT POINTS THE & VECTOR AT THE PROGRAM (& RUNS IT AGAIN), SETS UP
* THE JMP VECTORS AT $58 (FLOAT THE INTEGER ACCUMULATOR) AND $5B
* (ONERR), FINDS THE LIBRARY'S OWN ADDRESS FROM THE OPERAND OF THE
* CALLER'S JSR, SO THE LIBRARY RUNS WHEREVER IT IS LOADED, PATCHES
* CHRGET FOR ONERR, COPIES THE HEADER TO PAGE ZERO AND CLEARS THE
* VARIABLES. IT RETURNS PAST THE HEADER.
*--------------------------------------
INIT     JSR  CROUT1                    ;CLEAR TO THE END OF THE LINE, NEW LINE
         LDA  #$4C                      ;$4C, JMP, FOR THE THREE VECTORS
         STA  AMPER                     ;& VECTOR
         STA  ERRVEC                    ;ONERR VECTOR AT $5B
         STA  FLTVEC                    ;FLOAT VECTOR AT $58
         PLA                            ;THE CALLER'S RETURN ADDRESS: THE LAST BYTE OF ITS JSR
         TAX
         CLC
         ADC  #$11                      ;+$11: PAST THE 17-BYTE HEADER
         TAY
         PLA                            ;HIGH BYTE
         STA  AMPER+2
         STA  RESULT+1                  ;RESULT WILL POINT AT THE CALLER'S JSR
         ADC  #$00                      ;PUSH THE ADDRESS AFTER THE HEADER FOR THE FINAL RTS
         PHA
         TYA
         PHA
         CPX  #$02                      ;THE JSR BEGINS 2 BYTES BEFORE: BORROW IF THE LOW BYTE IS BELOW 2
         BCS  INIT1
         DEC  AMPER+2
         DEC  RESULT+1
INIT1    DEX                            ;LOW BYTE - 2
         DEX
         STX  AMPER+1                   ;THE & VECTOR JUMPS TO THE PROGRAM'S START: & RUNS IT AGAIN
         STX  RESULT                    ;RESULT = ADDRESS OF THE CALLER'S JSR INIT
         LDY  #$BB                      ;ONERR TEXT POINTER = $00BB, INSIDE THE CHRGET PATCH
         STY  TXTPSV
         LDY  #$00
         STY  TXTPSV+1
         STY  CURLIN+1                  ;NO STATEMENT ADDRESS YET
         STY  CURLIN
         STY  ERRFLG                    ;ONERR OFF
         INY                            ;THE JSR'S OPERAND IS THIS LIBRARY'S ADDRESS, L
         LDA  (RESULT),Y
         CLC
         ADC  #$69                      ;L+$169 = CHRPATCH
         STA  RETADR
         TAX
         INY
         LDA  (RESULT),Y
         ADC  #$01
         STA  RETADR+1
         TAY
         TXA
         ADC  #$44                      ;L+$1AD = $09B0, THE FOR MARKER (SEE FORUNWND)
         STA  FORPOP
         TYA
         ADC  #$00
         STA  FORPOP+1
         TXA                            ;L+$0E6B = FLOATI: $58 IS NOW JMP FLOATI
         ADC  #$02
         STA  FLTVEC+1
         TYA
         ADC  #$0D
         STA  FLTVEC+2
         LDY  #$0E                      ;COPY THE 15 BYTES OF THE PATCH TO $BA-$C8
INIT2    LDA  (RETADR),Y
         STA  CHRPAT,Y
         DEY
         BPL  INIT2
         LDA  #$55                      ;APPLESOFT'S TEMPORARY STRING STACK, EMPTY
         STA  TEMPPT
         LDA  #$06                      ;$33 = 6
         STA  PROMPT
         LDY  #$13                      ;OFFSET 19 FROM THE JSR: THE COMMON FLAG
         LDA  (RESULT),Y
         STA  HDRFLAG
INIT3    DEY                            ;THE HEADER, LAST WORD FIRST
         LDA  (RESULT),Y
         CPY  #$0D                      ;OFFSETS 13-18: THE LOCAL BOUNDS TO $7B-$80
         BCC  INIT4
         STA  STRCEND+1,Y
         BCS  INIT3
INIT4    CPY  #$07                      ;OFFSETS 7-12: THE COMMON BOUNDS TO $69-$6E ...
         BCC  INIT6
         BIT  HDRFLAG                   ;... A PROGRAM THAT USES COMMON MUST FIND THEM AS THE PROGRAM BEFORE LEFT THEM
         BPL  INIT5
         CMP  RESULT,Y
         BEQ  INIT3
         LDX  #$A3                      ;A DIFFERENT COMMON BLOCK: ERROR $A3 (163, TYPE MISMATCH)
         BNE  CLEAR5
INIT5    STA  RESULT,Y                  ;NO COMMON OR DEFCOMMON: SET THEM
         BPL  INIT3
INIT6    STA  NUMDIM,Y                  ;OFFSETS 3-6: THE FIRST DATA ITEM AND THE HIGHEST ADDRESS TO $12-$15
         CPY  #$03
         BNE  INIT3
         LDA  HDRFLAG                   ;MODE = THE COMMON FLAG: 0 CLEARS COMMON AND LOCALS, $FF ONLY THE LOCALS
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
*
*--------------------------------------
* CLRCOM: CLEAR COMMON (REM! CLEAR COMMON). CLEAR: THE CLEAR
* STATEMENT. BOTH, AND THE END OF INIT, SHARE ONE ROUTINE WITH A IN
* THE ROLE OF A MODE: 1 CLEARS THE COMMON BLOCK, $FF THE LOCAL
* VARIABLES, 0 BOTH (INIT, NO COMMON OR DEFCOMMON).
* NUMERIC VARIABLES BECOME ZERO; STRING VARIABLES POINT AT AN EMPTY
* STRING KEPT AT HIMEM-1. MODE 0 ALSO EMPTIES STRING SPACE. THE
* ROUTINE ENDS BY RESETTING THE STACK (RESETSTK).
*--------------------------------------
CLRCOM   LDA  #$01                      ;MODE 1: THE COMMON BLOCK
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
CLEAR    LDA  #$FF                      ;MODE $FF: THE LOCAL VARIABLES
         LDY  MEMSIZ                    ;HIMEM
         LDX  MEMSIZ+1
         STX  HDRFLAG                   ;NOT ZERO: CLEAR VARIABLES AFTERWARDS
CLEAR1   PHA                            ;KEEP THE MODE
         TYA
         BNE  CLEAR2
         DEX
CLEAR2   DEY
         STX  STRPSH+1                  ;STRPSH = HIMEM-1, AN EMPTY STRING (ITS LENGTH BYTE IS SET BELOW)
         STY  STRPSH
         PLA                            ;MODE 0: ALSO EMPTY STRING SPACE ...
         PHA
         BNE  CLEAR4
         TYA
         BNE  CLEAR3
         DEX
CLEAR3   DEY
         STX  FRETOP+1                  ;... FRETOP = HIMEM-2
         STY  FRETOP
CLEAR4   LDY  FRETOP                    ;STRING SPACE MUST STAY ABOVE THE PROGRAM AND ITS VARIABLES
         CPY  HIGHEST
         LDA  FRETOP+1
         SBC  HIGHEST+1
         BCS  HIMEM2
         PLA
         LDX  #$4D                      ;ELSE OUT OF MEMORY, ERROR $4D
CLEAR5   BNE  HIMEM10                   ;ON TO THE ERROR EXIT (X = ERROR NUMBER)
         JSR  FLTVEC                    ;INTEGER ENTRY: FLOAT THE INTEGER ACCUMULATOR FIRST
*
*--------------------------------------
* HIMEM: (THE STATEMENT): THE NEW HIMEM ADDRESS IS IN FAC. STRING
* SPACE IS EMPTIED BELOW IT; VARIABLES ARE NOT CLEARED.
*--------------------------------------
HIMEM    JSR  GETADR                    ;THE ADDRESS IN FAC TO LINNUM
         LDX  LINNUM+1                  ;HIMEM = THE ADDRESS
         STX  MEMSIZ+1
         LDY  LINNUM
         STY  MEMSIZ
         LDA  #$00                      ;MODE 0 AND NO VARIABLE CLEARING
         STA  HDRFLAG
         BEQ  CLEAR1
HIMEM1   PLA
         RTS
HIMEM2   LDY  #$00                      ;THE EMPTY STRING: LENGTH 0
         TYA
         STA  (STRPSH),Y
         LDA  HDRFLAG                   ;HIMEM: DONE
         BEQ  HIMEM1
         LDX  #$00
         PLA
HIMEM3   PHA                            ;CLEAR ONE BLOCK: X = 0 THE COMMON BOUNDS ...
         BPL  HIMEM4
         LDX  #$12                      ;... X = $12 THE LOCAL BOUNDS ($7B-$80)
HIMEM4   LDA  COMBEG+1,X                ;A1 = THE BLOCK'S START-1
         STA  A1L+1
         LDA  COMBEG,X
         STA  A1L
         LDY  #$00
HIMEM5   INC  A1L                       ;NUMBERS: ZERO EVERY BYTE UP TO THE NUMERIC END
         BNE  HIMEM6
         INC  A1L+1
HIMEM6   LDA  NUMCEND,X
         CMP  A1L
         LDA  NUMCEND+1,X
         SBC  A1L+1
         BCC  HIMEM7
         TYA
         STA  (A1L),Y
         BEQ  HIMEM5
HIMEM7   LDA  A1L                       ;STRINGS: EVERY POINTER UP TO THE STRING END ...
         CMP  STRCEND,X
         LDA  A1L+1
         SBC  STRCEND+1,X
         BCS  HIMEM9
         LDA  STRPSH                    ;... POINTS AT THE EMPTY STRING
         STA  (A1L),Y
         INC  A1L
         BNE  HIMEM8
         INC  A1L+1
HIMEM8   LDA  STRPSH+1
         STA  (A1L),Y
         INC  A1L
         BNE  HIMEM7
         INC  A1L+1
         BNE  HIMEM7
HIMEM9   PLA                            ;MODE 0: NOW THE LOCALS TOO
         BNE  RESETSTK
         LDA  #$FF
         BMI  HIMEM3
HIMEM10  BNE  POP7                      ;ON TO THE ERROR EXIT
*
*--------------------------------------
* RESETSTK: EMPTY THE STACK, DROPPING EVERY PENDING GOSUB AND FOR,
* AND RESET THE DATA POINTER. THE BOTTOM OF THE NEW STACK IS A
* RETURN ADDRESS INTO NORET, SO A RETURN WITH NO GOSUB REPORTS
* RETURN WITHOUT GOSUB. PASS 0, 1 AND 2 OF THE COMPILER CALL THIS
* ROUTINE AFTER AN ERROR.
*--------------------------------------
RESETSTK PLA                            ;THE CALLER'S RETURN ADDRESS
         STA  RESULT
         PLA
         STA  RESULT+1
         LDX  #$FF                      ;AN EMPTY STACK
         TXS
         LDA  FORPOP                    ;PUSH FORPOP+8 = $09B8, THE RTS BEFORE NORET: A RETURN WITHOUT GOSUB RETURNS TO NORET
         CLC
         ADC  #$08
         TAX
         LDA  FORPOP+1
         ADC  #$00
         PHA
         TXA
         PHA
         LDA  RESULT+1                  ;AND THE CALLER'S RETURN ADDRESS
         PHA
         LDA  RESULT
         PHA
*
*--------------------------------------
* RESTORE: POINT THE DATA POINTER AT THE FIRST DATA ITEM.
*--------------------------------------
RESTORE  LDA  DATFIRST                  ;DATA POINTER = FIRST DATA ITEM
         STA  DATPTR
         LDA  DATFIRST+1
         STA  DATPTR+1
         RTS
*
*--------------------------------------
* CHRPATCH: 15 BYTES THAT INIT COPIES OVER CHRGET AT $BA-$C8. THEY
* RUN THERE, SO THEY ARE SHOWN AS THEY RUN AT $BA.
* FOR THE INTERPRETER NOTHING CHANGES: SPACES ARE SKIPPED AND THE
* ROM'S CHRGET GOES ON AT $F114. BUT WHEN THE ROM'S ERROR HANDLER,
* WITH ONERR ACTIVE, SETS THE TEXT POINTER TO $00BB (TXTPSV, SET BY
* INIT) AND CALLS CHRGOT, THE BYTE READ IS THE $20 OF THE PATCH'S
* OWN CMP, THE TEXT POINTER IS ON PAGE ZERO, AND THE PATCH JUMPS
* THROUGH THE ONERR VECTOR AT $5B INTO THE COMPILED HANDLER.
*--------------------------------------
CHRPATCH DFB  $C9,$20                   ;$BA: CMP #$20
         DFB  $D0,$08                   ;$BC: BNE $00C6
         DFB  $A5,$B9                   ;$BE: LDA $B9
         DFB  $D0,$EF                   ;$C0: BNE $00B1
         DFB  $E6,$B9                   ;$C2: INC $B9
         DFB  $D0,$95                   ;$C4: BNE $005B
         DFB  $4C,$14,$F1               ;$C6: JMP $F114
*
*--------------------------------------
* POP (THE STATEMENT): DROP THE MOST RECENT GOSUB RETURN ADDRESS,
* PASSING OVER ANY FOR FRAMES ABOVE IT. ERROR RETURN WITHOUT GOSUB
* IF THERE IS NONE.
*--------------------------------------
POP      PLA                            ;THE CALLER'S RETURN ADDRESS
         STA  RESULT
         PLA
         STA  RESULT+1
         TSX
POP1     LDY  #$03                      ;Y = 3: FINDFOR GOES ON AT POP2
         BNE  FINDFOR
POP2     BCC  POP3                      ;A FOR FRAME: DROP IT AND LOOK AGAIN
         TXS
         BCS  POP1
POP3     LDA  FORPOP                    ;IS THE TOP THE STACK'S BOTTOM ENTRY (THE RETURN TO NORET)?
         ADC  #$08
         TAY
         LDA  FORPOP+1
         ADC  #$00
         TSX
         CMP  STACK+2,X                 ;COMPARE HIGH BYTE ...
         BNE  POP4
         TYA
         CMP  STACK+1,X                 ;... AND LOW BYTE
         SEC
         BEQ  POP5
POP4     CLC                            ;NO: DROP THE GOSUB RETURN ADDRESS
         PLA
         PLA
POP5     LDA  RESULT+1                  ;RETURN TO THE CALLER
         PHA
         LDA  RESULT
         PHA
         BCS  POP6
         RTS
POP6     LDX  #$16                      ;RETURN WITHOUT GOSUB: ERROR $16
POP7     BNE  FINDF3                    ;ON TO THE ERROR EXIT
*
*--------------------------------------
* FORUNWND: EVERY FOR FRAME STARTS WITH THE ADDRESS IN FORPOP
* ($09B0), WHICH IS ALSO A RETURN ADDRESS. WHEN A SUBROUTINE RETURNS
* WITH UNFINISHED LOOPS ON THE STACK, ITS RTS PULLS THAT ADDRESS AND
* COMES HERE, ONE PAST IT: THE REST OF THE FRAME IS DROPPED AND RTS
* IS TRIED AGAIN, SO RETURN UNWINDS THE LOOPS.
*--------------------------------------
FORUNWND TSX                            ;THE MARKER'S 2 BYTES ARE GONE; DROP THE OTHER 14 ...
         TXA
         CLC
         ADC  #$0E
         TAX
         TXS
         RTS                            ;... AND RETURN AGAIN
*
*--------------------------------------
* NORET: RETURN WITHOUT GOSUB. RESETSTK LEAVES A RETURN ADDRESS TO
* HERE AT THE BOTTOM OF THE STACK.
*--------------------------------------
NORET    LDX  #$16                      ;ERROR $16: RETURN WITHOUT GOSUB
         JMP  ERROR
*
*--------------------------------------
* FINDFOR: IS THERE A FOR FRAME ON THE STACK AT X? CARRY SET IF THE
* 16 BYTES ABOVE X START WITH THE FOR MARKER. SHARED BY NEXT (Y =
* 1), FOR (Y = 2) AND POP (Y = 3); Y SAYS WHERE TO GO ON.
*--------------------------------------
FINDFOR  TXA                            ;X+16: THE STACK ABOVE THE FRAME
         CLC
         ADC  #$10
         BCS  FINDF1                    ;NOT 16 BYTES LEFT: NO FRAME
         TAX
         DFB  $BD,$F1,$00               ;LDA $00F1,X (ABSOLUTE ON PURPOSE); THE FRAME'S FIRST TWO BYTES ...
         CMP  FORPOP                    ;... ARE THEY THE MARKER?
         BNE  FINDF1
         DFB  $BD,$F2,$00               ;LDA $00F2,X (ABSOLUTE ON PURPOSE)
         CMP  FORPOP+1
         BEQ  FINDF2
FINDF1   CLC                            ;CARRY CLEAR: NO FRAME
FINDF2   DEY                            ;Y = 1: NEXT, 2: FOR, 3: POP
         BEQ  NEXT2
         DEY
         BEQ  FORIN5
         BNE  POP2
FINDF3   BNE  NEXT3                     ;ON TO THE ERROR EXIT
*
*--------------------------------------
* FOR, THE START OF A LOOP. FOUR ENTRIES BY THE LOOP VARIABLE'S TYPE
* AND THE INITIAL VALUE'S: IFORINR INTEGER VARIABLE, REAL VALUE;
* IFORINIT BOTH INTEGER; FORINITI REAL VARIABLE, INTEGER VALUE;
* FORINIT BOTH REAL. THE CALL IS FOLLOWED BY THE VARIABLE'S ADDRESS.
* THE VALUE IS STORED IN THE VARIABLE; A FRAME FOR THE SAME VARIABLE
* STILL ON THE STACK IS REMOVED (AS IN APPLESOFT); THE VARIABLE'S
* ADDRESS IS PUSHED AS THE FIRST PART OF THE NEW FRAME. THE LIMIT
* AND STEP ROUTINES PUSH THE REST.
*--------------------------------------
IFORINR  JSR  AYINT                     ;REAL VALUE TO AN INTEGER IN IACC
IFORINIT LDX  #$01                      ;X = 1: STORE IACC
         BNE  FORIN1
FORINITI JSR  FLTVEC                    ;INTEGER VALUE TO A REAL IN FAC
FORINIT  LDX  #$00                      ;X = 0: STORE FAC
FORIN1   PLA                            ;THE RETURN ADDRESS POINTS BEFORE THE INLINE WORD
         STA  RETADR
         PLA
         STA  RETADR+1
         LDY  #$01                      ;TPTR = THE LOOP VARIABLE'S ADDRESS
         LDA  (RETADR),Y
         STA  TPTR
         INY
         LDA  (RETADR),Y
         STA  TPTR+1
         DEX                            ;INTEGER: STORE IACC, HIGH BYTE FIRST
         BMI  FORIN2
         LDY  #$00
         LDA  IACC
         STA  (TPTR),Y
         INY
         LDA  IACC+1
         STA  (TPTR),Y
         TYA
         BNE  FORIN3
FORIN2   TAY                            ;REAL: STORE FAC ROUNDED AT (Y,X)
         LDX  TPTR
         JSR  MOVMF
FORIN3   TSX                            ;LOOK FOR A FRAME FOR THE SAME VARIABLE
FORIN4   LDY  #$02
         BNE  FINDFOR
FORIN5   BCC  FORIN6                    ;A FRAME: IS IT FOR THIS VARIABLE?
         DFB  $BD,$FF,$00               ;LDA $00FF,X (ABSOLUTE ON PURPOSE)
         CMP  TPTR
         BNE  FORIN4
         LDA  STACK,X
         CMP  TPTR+1
         BNE  FORIN4
         TXS                            ;YES: DROP IT
FORIN6   LDA  TPTR+1                    ;START THE NEW FRAME: THE VARIABLE'S ADDRESS
         PHA
         LDA  TPTR
         PHA
         CLC
         BCC  NEXT7                     ;AND RETURN PAST THE INLINE WORD
*
*--------------------------------------
* NEXT: THE CALL IS FOLLOWED BY THE VARIABLE'S ADDRESS, 0 FOR A BARE
* NEXT. FRAMES OF INNER LOOPS ARE DROPPED UNTIL THE VARIABLE'S FRAME
* IS FOUND (ERROR NEXT WITHOUT FOR IF NONE). THE STEP IS ADDED TO
* THE VARIABLE AND THE RESULT COMPARED WITH THE LIMIT IN THE
* DIRECTION OF THE STEP: THE LOOP GOES ON BY RETURNING TO THE LOOP
* ADDRESS KEPT IN THE FRAME, OR ENDS BY DROPPING THE FRAME AND
* RETURNING PAST THE CALL.
* FOR FRAME, 16 BYTES FROM THE TOP: MARKER (FORPOP), LOOP ADDRESS-1,
* STEP (5 BYTES PACKED), LIMIT (5), VARIABLE ADDRESS. AN INTEGER
* LOOP HAS 0 IN THE 4TH BYTE, THE STEP IN BYTES 5-6, THE LOOP
* ADDRESS IN 8-9 AND THE LIMIT IN 10-11.
*--------------------------------------
NEXT     PLA                            ;THE RETURN ADDRESS POINTS BEFORE THE INLINE WORD
         STA  RETADR
         PLA
         STA  RETADR+1
         TSX
NEXT1    TXS                            ;DROP THE FRAME AT X (AN INNER LOOP) AND LOOK FURTHER
         LDY  #$01
         BNE  FINDFOR
NEXT2    LDY  #$02                      ;Y = 2: THE HIGH BYTE OF THE INLINE ADDRESS
         BCS  NEXT4                     ;A FRAME
         LDA  RETADR+1                  ;NONE: NEXT WITHOUT FOR (ERROR 0)
         PHA
         LDA  RETADR
         PHA
         LDX  #$00
         TYA
NEXT3    BNE  NEXT8
NEXT4    LDA  (RETADR),Y                ;0: A BARE NEXT TAKES THE INNERMOST LOOP
         BEQ  NEXT5
         CMP  STACK,X                   ;THE FRAME'S VARIABLE?
         BNE  NEXT1
         DEY
         LDA  (RETADR),Y
         DFB  $DD,$FF,$00               ;CMP $00FF,X (ABSOLUTE ON PURPOSE)
         BNE  NEXT1
NEXT5    TSX                            ;THE FRAME IS AT X+1
         LDA  STACK+4,X                 ;A ZERO 4TH BYTE: AN INTEGER LOOP
         BEQ  NEXT9
         TXA                            ;REAL: FAC = STEP
         CLC
         ADC  #$05
         LDY  #$01
         JSR  MOVFM
         JSR  SIGN                      ;THE SIGN OF THE STEP
         STA  RESULT+3
         TSX                            ;FAC = STEP + VARIABLE
         LDY  $0110,X
         LDA  $010F,X
         JSR  FADD
         TSX                            ;STORE IT IN THE VARIABLE
         LDY  $0110,X
         LDA  $010F,X
         TAX
         JSR  MOVMF
         TSX                            ;COMPARE WITH THE LIMIT
         TXA
         CLC
         ADC  #$0A
         LDY  #$01
         JSR  FCOMP
         CMP  RESULT+3                  ;PAST THE LIMIT IN THE STEP'S DIRECTION: THE LOOP IS DONE
         BEQ  NEXT6
         TSX                            ;AGAIN: RETURN TO THE LOOP ADDRESS KEPT IN THE FRAME
         LDA  STACK+4,X
         PHA
         LDA  STACK+3,X
         PHA
         RTS
NEXT6    TSX                            ;DONE: DROP THE 16-BYTE FRAME
         TXA
         CLC
         ADC  #$10
         TAX
         TXS
NEXT7    LDA  RETADR                    ;RETURN PAST THE INLINE WORD
         ADC  #$02
         TAX
         LDA  RETADR+1
         ADC  #$00
         PHA
         TXA
         PHA
         RTS
NEXT8    BNE  NEXT10
NEXT9    LDA  STACK+5,X                 ;INTEGER LOOP: IACC = STEP
         STA  IACC
         LDA  $0106,X
         STA  IACC+1
         LDA  $010F,X                   ;RESULT = THE VARIABLE'S ADDRESS
         STA  RESULT
         LDA  $0110,X
         STA  RESULT+1
         LDY  #$01                      ;VARIABLE += STEP, LOW BYTE ...
         LDA  (RESULT),Y
         CLC
         ADC  IACC+1
         STA  (RESULT),Y
         STA  IACC+1
         DEY                            ;... HIGH BYTE
         LDA  (RESULT),Y
         ADC  IACC
         BVC  NEXT11                    ;OVERFLOW: ERROR $45
         LDX  #$45
NEXT10   BNE  NEXT17
NEXT11   STA  (RESULT),Y
         TAY
         EOR  $010A,X                   ;SAME SIGN AS THE LIMIT?
         BPL  NEXT13
         TYA
         BPL  NEXT16
NEXT12   LDA  STACK+5,X
         BPL  NEXT15
         BMI  NEXT6
NEXT13   TYA
         CMP  $010A,X
NEXT14   BCC  NEXT12
         BNE  NEXT16
         LDA  IACC+1
         CMP  $010B,X
         BNE  NEXT14
NEXT15   LDA  $0109,X                   ;NOT PAST THE LIMIT: BACK TO THE LOOP
         PHA
         LDA  $0108,X
         PHA
         RTS
NEXT16   LDA  STACK+5,X
         BMI  NEXT15
         BPL  NEXT6
NEXT17   BNE  ARRDIM2
*
*--------------------------------------
* ARRAY ELEMENTS. EVERY ARRAY HAS A ROUTINE IN THE PROGRAM: SEC
* (LOAD) OR CLC (ADDRESS) THEN JSR ARRREAL, ARRSTR OR ARRINT,
* FOLLOWED BY THE ARRAY'S DESCRIPTOR: ITS ADDRESS, THE NUMBER OF
* DIMENSIONS AND THE HIGHEST INDEX OF EACH, LAST DIMENSION FIRST.
* THE FIRST SUBSCRIPT IS IN IACC; THE OTHERS WERE PUSHED BY PUSHSUB.
* EACH IS CHECKED AGAINST ITS HIGHEST INDEX (ERROR $6B, BAD
* SUBSCRIPT) AND THE OFFSET IS BUILT AS
* OFFSET*(HIGHEST+1)+SUBSCRIPT, THEN SCALED BY THE ELEMENT SIZE (5
* REAL, 2 INTEGER OR STRING).
* LOAD: THE ELEMENT GOES TO FAC, IACC OR THE STRING ACCUMULATOR.
* ADDRESS: THE ELEMENT'S ADDRESS GOES TO $DC/$DD AND ITS TYPE TO $D9
* FOR ARRSTORE, WHICH STORES THE VALUE COMPUTED IN BETWEEN.
*--------------------------------------
ARRREAL  LDX  #$00                      ;X = ELEMENT TYPE: 0 REAL ...
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
ARRSTR   LDX  #$02                      ;... 2 STRING ...
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
ARRINT   LDX  #$01                      ;... 1 INTEGER
         PHP                            ;KEEP THE CARRY: 1 LOAD, 0 ADDRESS
         PLA
         STA  RESULT+2
         STX  RESULT+3                  ;AND THE TYPE
         PLA                            ;TPTR = THE DESCRIPTOR - 1 (THE ROUTINE'S RETURN ADDRESS)
         STA  TPTR
         PLA
         STA  TPTR+1
         PLA                            ;RETADR = THE COMPILED CODE'S RETURN ADDRESS
         STA  RETADR
         PLA
         STA  RETADR+1
         LDA  IACC                      ;THE FIRST SUBSCRIPT JOINS THE OTHERS ON THE STACK
         PHA
         LDA  IACC+1
         PHA
         LDY  #$00                      ;OFFSET = 0
         STY  IACC+1
         STY  IACC
         LDY  #$03                      ;Y = 2 * DIMENSIONS + 3: THE LAST HIGHEST INDEX
         LDA  (TPTR),Y
         ASL
         TAY
         INY
         INY
ARRDIM   INY                            ;EACH DIMENSION: ADD THE NEXT SUBSCRIPT TO THE OFFSET
         PLA
         TAX
         CLC
         ADC  IACC+1
         STA  IACC+1
         PLA
         PHA
         ADC  IACC
         STA  IACC
         PLA                            ;CHECK IT AGAINST THE HIGHEST INDEX
         CMP  (TPTR),Y
         BCC  ARRSUB
         BNE  ARRDIM1
         DEY
         TXA
         CMP  (TPTR),Y
         BCC  ARRSUB1
         BEQ  ARRSUB1
ARRDIM1  LDA  RETADR+1                  ;TOO LARGE (OR NEGATIVE): BAD SUBSCRIPT, ERROR $6B
         PHA
         LDA  RETADR
         PHA
         LDX  #$6B
ARRDIM2  BNE  ARRAD1
ARRSUB   DEY                            ;NEXT DIMENSION
ARRSUB1  DEY
         DEY
         CPY  #$02                      ;ALL DONE
         BEQ  ARRSIZE
         STY  TEMP3+4                   ;OFFSET *= HIGHEST+1 OF THE NEXT DIMENSION
         LDA  (TPTR),Y
         CLC
         ADC  #$01
         STA  IARG+1
         INY
         LDA  (TPTR),Y
         ADC  #$00
         STA  IARG
         LDX  #$00                      ;X = 0 (KEPT IN $16): MULSHARE COMES BACK TO $0B81
         BEQ  MULSHARE
ARRSUB2  LDY  TEMP3+4
         BNE  ARRDIM
ARRSIZE  LDX  RESULT+3                  ;TIMES THE ELEMENT SIZE: 2 ...
         BEQ  ARRSI1
         ASL  IACC+1
         ROL  IACC
         BCC  ARRADDR
ARRSI1   LDY  IACC                      ;... OR 5 (4+1) FOR A REAL
         LDA  IACC+1
         STA  HDRFLAG
         ASL
         ROL  IACC
         ASL
         ROL  IACC
         ADC  HDRFLAG
         STA  IACC+1
         TYA
         ADC  IACC
         STA  IACC
ARRADDR  LDA  RETADR+1                  ;RETURN ADDRESS BACK FOR THE COMPILED CODE
         PHA
         LDA  RETADR
         PHA
         LDY  #$01                      ;ELEMENT ADDRESS = ARRAY ADDRESS + OFFSET
         CLC
         LDA  IACC+1
         ADC  (TPTR),Y
         TAX
         INY
         LDA  IACC
         ADC  (TPTR),Y
         TAY
         TXA
         LDX  RESULT+3
         LSR  RESULT+2                  ;LOAD?
         BCS  MULSH1
         STY  ERRPOS+1                  ;NO: KEEP THE ADDRESS AND TYPE FOR ARRSTORE
         STA  ERRPOS
         STX  ELTYPE
         RTS
ARRAD1   BNE  MULLO3
*
*--------------------------------------
* IMULT: INTEGER OPERATION 4: IACC = IACC * THE INTEGER AT (Y,A).
* SIGNS ARE TAKEN OUT (COUNTED IN $AB), THE MAGNITUDES MULTIPLIED BY
* SHIFT AND ADD, AND THE SIGN PUT BACK. ERROR $45 (OVERFLOW) IF THE
* PRODUCT DOES NOT FIT. MULSHARE IS THE SAME MULTIPLY WITHOUT SIGNS,
* USED BY THE ARRAY CODE.
*--------------------------------------
IMULT    STY  RESULT+1                  ;THE VARIABLE INTO IARG
         STA  RESULT
         LDY  #$00
         LDA  (RESULT),Y
         STA  IARG
         INY
         LDA  (RESULT),Y
         STA  IARG+1
         LDX  #$02                      ;MAKE IARG AND IACC POSITIVE, COUNTING NEGATIVES
         STX  SGNCPR
IMULT1   LDA  IARG,X
         BPL  IMULT3
IMULT2   BPL  ARRSUB2
         DEC  SGNCPR                    ;ONE MORE NEGATIVE
         LDA  #$00
         SEC
         SBC  IARG+1,X
         STA  IARG+1,X
         LDA  #$00
         SBC  IARG,X
         STA  IARG,X
         BVS  MULLO2                    ;-32768 HAS NO POSITIVE: OVERFLOW
IMULT3   DEX
         DEX
         BEQ  IMULT1
MULSHARE STX  HDRFLAG                   ;THE SMALLER FACTOR GOES IN THE SHIFT REGISTER
         LDX  IARG+1
         CPX  IACC+1
         LDA  IARG
         SBC  IACC
         BCS  MULSH2
         LDY  IARG
         LDA  IACC
         STA  IARG
         LDA  IACC+1
         STA  IARG+1
         BCC  MULSH3
MULSH1   BCS  ARRLOAD
MULSH2   LDY  IACC
         LDX  IACC+1
MULSH3   STY  FACSIGN                   ;Y,X: THE MULTIPLIER, SHIFTED OUT BIT BY BIT
         STX  SERLEN
         LDA  #$00                      ;PRODUCT = 0
         STA  IACC
         STA  IACC+1
MULLOOP  LSR  FACSIGN                   ;NEXT BIT OF THE MULTIPLIER
         ROR  SERLEN
         BCC  MULLO1
         LDA  IARG+1                    ;SET: ADD THE MULTIPLICAND
         CLC
         ADC  IACC+1
         STA  IACC+1
         LDA  IARG
         ADC  IACC
         STA  IACC
         BMI  MULLO2                    ;PAST 32767: OVERFLOW
MULLO1   LDA  FACSIGN                   ;NO BITS LEFT: DONE
         ORA  SERLEN
         BEQ  MULLO5
         ASL  IARG+1                    ;MULTIPLICAND * 2
         ROL  IARG
         BPL  MULLOOP
MULLO2   LDX  #$45                      ;OVERFLOW: ERROR $45
MULLO3   BNE  DISPS2
MULLO4   BEQ  IMULT
MULLO5   BIT  HDRFLAG                   ;FROM THE ARRAY CODE: BACK TO IT
         BPL  IMULT2
         DEC  SGNCPR                    ;ONE NEGATIVE FACTOR: NEGATE THE PRODUCT
         BEQ  INEG
         RTS
*
*--------------------------------------
* ARRLOAD: LOAD THE ELEMENT AT (Y,A) BY ITS TYPE (X: 0 REAL, 1
* INTEGER, 2 STRING).
*--------------------------------------
ARRLOAD  DEX                            ;REAL ...
         BPL  ARRLO1
         JSR  MOVFM                     ;FAC = THE ELEMENT, FLAGS SET
         LDA  ARGSIGN
         JMP  SGNEXIT
ARRLO1   BEQ  ILOAD                     ;INTEGER: ILOAD ...
         STY  RESULT+1                  ;... STRING: BOTH STRING ACCUMULATORS
         STA  RESULT
         LDY  #$00
         LDA  (RESULT),Y
         STA  STRACC
         STA  STRPSH
         INY
         LDA  (RESULT),Y
         STA  STRACC+1
         STA  STRPSH+1
         RTS
*
*--------------------------------------
* ARRSTORE: STORE THE VALUE INTO THE ARRAY ELEMENT WHOSE ADDRESS AND
* TYPE THE ARRAY ROUTINE LEFT IN $DC/$DD AND $D9.
*--------------------------------------
ARRSTORE LDY  ERRPOS+1                  ;THE ELEMENT'S ADDRESS ...
         LDA  ERRPOS
         LDX  ELTYPE                    ;... AND TYPE
         BNE  ARRST1
         TAX                            ;REAL: STORE FAC ROUNDED
         JMP  MOVMF
ARRST1   DEX                            ;INTEGER: STORE IACC; STRING: FALL INTO THE STRING STORE WITH CARRY CLEAR
         BEQ  ISTORE
         CLC
*
*--------------------------------------
* DISPSTR: THE STRING VARIABLE DISPATCHER. A STRING VARIABLE'S
* ROUTINE IS SEC (OR CLC), LDA #, LDY #HIGH, LDA #LOW, JMP DISPSTR:
* CARRY SET LOADS THE VARIABLE'S POINTER INTO THE STRING ACCUMULATOR
* $77/$78, CARRY CLEAR STORES IT.
*--------------------------------------
DISPSTR  STA  TPTR
         STY  TPTR+1
         LDY  #$00
         BCC  DISPS1                    ;CARRY CLEAR: STORE
         LDA  (TPTR),Y                  ;LOAD: THE VARIABLE'S POINTER INTO $77/$78
         STA  STRACC
         INY
         LDA  (TPTR),Y
         STA  STRACC+1
         RTS
DISPS1   LDA  STRACC                    ;STORE: $77/$78 INTO THE VARIABLE
         STA  (TPTR),Y
         INY
         LDA  STRACC+1
         STA  (TPTR),Y
         RTS
DISPS2   BNE  ISUBT2
DISPS3   BEQ  MULLO4
*
*--------------------------------------
* INTEGER OPERATIONS 0 AND 1, ENTERED FROM DISPINT WITH (Y,A) = THE
* VARIABLE'S ADDRESS. INTEGERS ARE STORED HIGH BYTE FIRST. BOTH
* LEAVE THE FLAGS SET BY THE VALUE.
*--------------------------------------
ILOAD    STY  RESULT+1                  ;LOAD IACC FROM THE VARIABLE
         STA  RESULT
         LDY  #$00
         LDA  (RESULT),Y
         STA  IACC
         INY
         LDA  (RESULT),Y
         STA  IACC+1
         ORA  IACC
         RTS
ISTORE   STY  RESULT+1                  ;STORE IACC IN THE VARIABLE
         STA  RESULT
         LDY  #$00
         LDA  IACC
         STA  (RESULT),Y
         INY
         LDA  IACC+1
         STA  (RESULT),Y
         ORA  IACC
         RTS
*
*--------------------------------------
* INEG: IACC = -IACC. IRSUB (INTEGER OPERATION 3): IACC = VARIABLE -
* IACC. ISUBT: IACC = IARG - IACC. IADD (OPERATION 2): IACC = IACC +
* VARIABLE. ERROR $45 ON OVERFLOW.
*--------------------------------------
INEG     LDA  #$00                      ;IARG = 0, THEN 0 - IACC
         STA  IARG
         STA  IARG+1
         BEQ  ISUBT
IRSUB    STY  RESULT+1                  ;IARG = THE VARIABLE
         STA  RESULT
         LDY  #$00
         LDA  (RESULT),Y
         STA  IARG
         INY
         LDA  (RESULT),Y
         STA  IARG+1
ISUBT    LDA  IARG+1                    ;IACC = IARG - IACC
         SEC
         SBC  IACC+1
         STA  IACC+1
         LDA  IARG
         SBC  IACC
         STA  IACC
         BVC  IADD1
ISUBT1   LDX  #$45                      ;OVERFLOW: ERROR $45
ISUBT2   BNE  ICOMP5
IADD     STY  RESULT+1                  ;IACC = IACC + THE VARIABLE
         STA  RESULT
         LDY  #$00
         LDA  (RESULT),Y
         TAX
         INY
         LDA  (RESULT),Y
         CLC
         ADC  IACC+1
         STA  IACC+1
         TXA
         ADC  IACC
         STA  IACC
         BVS  ISUBT1
IADD1    RTS
*
*--------------------------------------
* DISPINT: THE INTEGER VARIABLE DISPATCHER. A NUMERIC VARIABLE'S
* ROUTINE LOADS X WITH THE OPERATION AND (Y,A) WITH THE VARIABLE'S
* ADDRESS AND JUMPS HERE.
* 0 LOAD IACC, 1 STORE IACC, 2 ADD, 3 VARIABLE MINUS IACC, 4
* MULTIPLY, 5 COMPARE; 6-13 ARE THE REAL OPERATIONS 0-7 WITH THE
* VARIABLE USED AS A REAL: 6 LOAD FAC, 7 STORE FAC (ROUNDED, RANGE
* CHECKED), 8 ADD, 9 SUBTRACT, 10 MULTIPLY, 11 COMPARE, 12 LOAD ARG,
* 13 DIVIDE.
*--------------------------------------
DISPINT  DEX                            ;OPERATION 0
         BMI  ILOAD
         BEQ  ISTORE                    ;1
         DEX                            ;2
         BEQ  IADD
         DEX                            ;3
         BEQ  IRSUB
         DEX                            ;4
         BEQ  DISPS3
         DEX                            ;5
         BEQ  ICOMP
         DEX                            ;6: LOAD AS A REAL
         BEQ  ICOMP6
         DEX                            ;7: STORE FAC
         BEQ  ISTOREF
         DEX                            ;8: ADD AS A REAL
         BEQ  ISTOR6
         DEX                            ;9: SUBTRACT: FAC = -FAC, THEN ADD
         BEQ  ISTOR5
         DEX                            ;10: MULTIPLY
         BEQ  ISTOR3
         DEX                            ;11: COMPARE
         BEQ  ISTOR1
         DEX                            ;12: LOAD ARG
         BEQ  ISTOR8
         LDX  #$01                      ;13: DIVIDE
         BNE  ISTOR9
DISPI1   LDA  FAC                       ;FAC = ARG / FAC
         JMP  FDIVT
*
*--------------------------------------
* ICOMP: INTEGER OPERATION 5: COMPARE IACC WITH THE VARIABLE. A =
* -1, 0 OR 1 AS FCOMP GIVES IT, FOR THE RELATIONS.
*--------------------------------------
ICOMP    STY  RESULT+1                  ;Y = HIGH BYTE, X = LOW BYTE OF THE VARIABLE
         STA  RESULT
         LDY  #$01
         LDA  (RESULT),Y
         TAX
         DEY
         LDA  (RESULT),Y
         TAY
         EOR  IACC                      ;DIFFERENT SIGNS: THE NEGATIVE ONE IS SMALLER
         BPL  ICOMP2
         TYA
         BMI  ICOMP4
ICOMP1   LDA  #$FF
         RTS
ICOMP2   CPY  IACC                      ;SAME SIGN: COMPARE HIGH, THEN LOW
ICOMP3   BCC  ICOMP4
         BNE  ICOMP1
         TXA
         SBC  IACC+1
         BNE  ICOMP3
         RTS
ICOMP4   LDA  #$01
         RTS
ICOMP5   BNE  ISTOR12
ICOMP6   BEQ  ISTOR13
*
*--------------------------------------
* ISTOREF: INTEGER OPERATION 7: STORE FAC IN THE INTEGER VARIABLE
* THROUGH APPLESOFT'S OWN LET, WHICH ROUNDS AND CHECKS THE RANGE.
*--------------------------------------
ISTOREF  STY  FORPNT+1                  ;THE VARIABLE'S ADDRESS FOR LET
         STA  FORPNT
         JMP  LET2
ISTOR1   LDX  #$03
         BNE  IREAL
ISTOR2   JSR  MOV1F                     ;COMPARE: THE OLD FAC (IN ARG) WITH THE VARIABLE
         JSR  MOVFA
         LDY  #$00
         LDA  #$93
         JMP  FCOMP
ISTOR3   LDX  #$02
         BNE  IREAL
ISTOR4   LDA  FAC                       ;FAC = ARG * FAC
         JMP  FMULTT
ISTOR5   PHA
         JSR  NEGOP
         PLA
ISTOR6   LDX  #$01
         BNE  IREAL
ISTOR7   LDA  FAC                       ;FAC = ARG + FAC
         JMP  FADDT
ISTOR8   LDX  #$00
ISTOR9   STX  RESULT+2
         LDX  #$04
         BNE  IREAL
ISTOR10  LDX  #$05                      ;LOAD ARG / DIVIDE: SWAP FAC AND ARG
ISTOR11  LDY  FAC,X
         LDA  ARG,X
         STY  ARG,X
         STA  FAC,X
         DEX
         BPL  ISTOR11
         LDX  RESULT+2
         BNE  DISPI1
         LDA  FAC
         RTS
ISTOR12  BNE  XDRAW3
ISTOR13  LDX  #$00
*
*--------------------------------------
* IREAL: THE REAL OPERATIONS ON AN INTEGER VARIABLE. X: 0 LOAD, 1
* ADD, 2 MULTIPLY, 3 COMPARE, 4 LOAD ARG OR (WITH $64 SET) DIVIDE.
* FOR ALL BUT A LOAD THE CURRENT FAC IS MOVED TO ARG; THE VARIABLE
* IS LOADED INTO FAC AS A REAL AND THE OPERATION APPLIED.
*--------------------------------------
IREAL    STX  HDRFLAG                   ;X: WHICH REAL OPERATION
         DEX
         BMI  IREAL1
         PHA                            ;THE CURRENT FAC TO ARG
         TYA
         PHA
         JSR  MOVAF
         PLA
         TAY
         PLA
IREAL1   STY  IACC+1                    ;VPNT = THE VARIABLE'S ADDRESS
         STA  IACC
         JSR  INTVAR                    ;FAC = THE INTEGER AS A REAL
         LDA  ARGSIGN
         JSR  SGNEXIT                   ;SIGNS COMPARED; A = THE EXPONENT
         LDX  HDRFLAG
         BNE  IREAL2                    ;A LOAD: DONE
         TAX
         RTS
IREAL2   DEX
         BEQ  ISTOR7
         DEX
         BEQ  ISTOR4
         DEX
         BEQ  ISTOR2
         BNE  ISTOR10
*
*--------------------------------------
* HI-RES: DRAW AND XDRAW AT X,Y, HPLOT TO AND HPLOT. EACH HAS A REAL
* ENTRY (JSR AYINT) AND AN INTEGER ENTRY 3 BYTES LATER. X WAS SAVED
* IN $50/$51 BY SAVEHX AND THE SHAPE NUMBER IN $F0; Y IS THE
* ARGUMENT NOW. X MUST BE BELOW 280 AND Y BELOW 192 (ERROR $35,
* ILLEGAL QUANTITY).
*--------------------------------------
DRAWAT   JSR  AYINT
DRAWATI  LDA  #$01
         BNE  XDRAW2
XDRAWAT  JSR  AYINT
XDRAWATI LDA  #$02
XDRAW2   STA  RESULT+3
         LDA  #$02
         BNE  HGRPOINT
XDRAW3   BNE  HGRPO5
HPLOTTO  JSR  AYINT
HPLOTTOI LDA  #$00
         BEQ  HGRPOINT
HPLOT    JSR  AYINT
HPLOTI   LDA  #$01
HGRPOINT STA  HDRFLAG                   ;$64: 0 HPLOT TO, 1 HPLOT, 2 DRAW/XDRAW AT
         JSR  CONINT2                   ;Y COORDINATE
         CPX  #$C0                      ;BELOW 192
         BCS  HGRPO4
         LDY  LINNUM+1                  ;X (SAVED IN $50/$51) BELOW 280
         LDX  LINNUM
         CPY  #$01
         BCC  HGRPO1
         BNE  HGRPO4
         CPX  #$18
         BCS  HGRPO4
HGRPO1   LDA  HDRFLAG
         BEQ  HGRPO3
         LDA  IACC+1                    ;HPLOT: POSITION AND PLOT
         DEC  HDRFLAG
         BEQ  HGRPO2
         JSR  HPOSN                     ;DRAW AT: POSITION, THEN DRAW SHAPE $F0
         LDX  FIRST
         LDA  #$01
         BNE  SHAPE1
HGRPO2   JMP  HPLOT0
HGRPO3   TXA                            ;HPLOT TO: A LINE TO X,Y
         PHA
         TYA
         TAX
         PLA
         LDY  IACC+1
         JMP  HGLIN
HGRPO4   LDX  #$35                      ;ILLEGAL QUANTITY: ERROR $35
HGRPO5   BNE  ASCFN1
*
*--------------------------------------
* DRAW AND XDRAW: THE SHAPE NUMBER IS CHECKED AGAINST THE COUNT AT
* THE START OF THE SHAPE TABLE, THE SHAPE'S ADDRESS LOOKED UP, AND
* THE ROM DRAWS IT WITH THE CURRENT ROTATION.
*--------------------------------------
DRAW     JSR  AYINT
DRAWI    LDA  #$01
         BNE  SHAPEARG
XDRAW    JSR  AYINT
XDRAWI   LDA  #$02
SHAPEARG STA  RESULT+3                  ;1 DRAW, 2 XDRAW
         JSR  CONINT2
SHAPE1   LDA  SHAPETBL                  ;THE SHAPE TABLE
         STA  HGRSHAPE
         LDA  SHAPETBL+1
         STA  HGRSHAPE+1
         TXA                            ;SHAPE NUMBER, NOT ABOVE THE COUNT IN THE TABLE'S FIRST BYTE
         LDX  #$00
         CMP  (HGRSHAPE,X)
         BEQ  SHAPE2
         BCS  HGRPO4
SHAPE2   ASL                            ;THE SHAPE'S OFFSET, 2 BYTES PER NUMBER ...
         BCC  SHAPE3
         INC  HGRSHAPE+1
         CLC
SHAPE3   TAY
         LDA  (HGRSHAPE),Y              ;... GIVES ITS ADDRESS
         ADC  HGRSHAPE
         TAX
         INY
         LDA  (HGRSHAPE),Y
         ADC  SHAPETBL+1
         STA  HGRSHAPE+1
         STX  HGRSHAPE
         LDA  HGRROT                    ;WITH THE CURRENT ROTATION
         DEC  RESULT+3
         BEQ  SHAPE4
         JMP  XDRAW1
SHAPE4   JMP  DRAW1
*
*--------------------------------------
* COLOR=. LIKE MOST STATEMENTS WITH ONE NUMBER, A REAL ENTRY (JSR
* AYINT) FALLS INTO THE INTEGER ENTRY, WHICH TAKES THE BYTE WITH
* CONINT AND GOES ON INTO THE ROM'S OWN CODE FOR THE STATEMENT.
*--------------------------------------
COLOR    JSR  AYINT
COLORI   JSR  CONINT2
         JMP  COLOR2
*
*--------------------------------------
* VALFN: VAL OF THE STRING ACCUMULATOR. THE BYTE AFTER THE STRING IS
* REPLACED BY 0 WHILE THE ROM'S FIN READS THE NUMBER, THEN PUT BACK.
*--------------------------------------
VALFN    LDY  #$00                      ;THE STRING'S LENGTH
         LDA  (STRACC),Y
         LDX  STRACC                    ;TXTPTR = THE STRING
         LDY  STRACC+1
         STX  TXTPTR
         STY  TXTPTR+1
         INX
         BNE  VALFN1
         INY
VALFN1   STX  RETADR                    ;RETADR = ITS TEXT
         STY  RETADR+1
         TAY                            ;THE BYTE AFTER THE TEXT ...
         STA  HDRFLAG
         LDA  (RETADR),Y
         PHA
         LDA  #$00                      ;... BECOMES 0 FOR NOW
         STA  (RETADR),Y
         JSR  CHRGET                    ;FIN READS THE NUMBER
         JSR  FIN
         PLA                            ;PUT THE BYTE BACK
         LDY  HDRFLAG
         STA  (RETADR),Y
         RTS
*
*--------------------------------------
* ASCFN: ASC OF THE STRING ACCUMULATOR INTO IACC (ERROR $35 FOR AN
* EMPTY STRING). LENFN: ITS LENGTH INTO IACC.
*--------------------------------------
ASCFN    LDY  #$00                      ;THE LENGTH
         LDA  (STRACC),Y
         BNE  ASCFN2
         LDX  #$35                      ;EMPTY: ERROR $35
ASCFN1   BNE  PRSTR3
ASCFN2   INY                            ;Y = 1: THE FIRST CHARACTER (THE BIT SKIPS LENFN'S LDY #0)
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
LENFN    LDY  #$00
         LDA  (STRACC),Y                ;IACC = THE BYTE
         STA  IACC+1
         LDY  #$00
         STY  IACC
         TAY
         RTS
*
*--------------------------------------
* STRLITP AND STRLIT: A STRING LITERAL IN THE CODE: THE CALL IS
* FOLLOWED BY THE LITERAL'S ADDRESS. THE STRING ACCUMULATOR POINTS
* AT IT (IT IS NOT COPIED) AND THE CALL RETURNS PAST THE WORD;
* STRLITP ALSO PRINTS IT (AN INPUT PROMPT).
*--------------------------------------
STRLITP  LDX  #$01                      ;X = 1: ALSO PRINT
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
STRLIT   LDX  #$00                      ;X = 0
         STX  HDRFLAG
         PLA                            ;THE RETURN ADDRESS POINTS BEFORE THE INLINE WORD
         STA  RESULT
         TAX
         PLA
         STA  RESULT+1
         LDY  #$01                      ;$77/$78 = THE LITERAL'S ADDRESS
         LDA  (RESULT),Y
         STA  STRACC
         INY
         LDA  (RESULT),Y
         STA  STRACC+1
         LDY  RESULT+1                  ;RETURN PAST THE WORD
         INX
         BNE  STRLIT1
         INY
STRLIT1  INX
         BNE  STRLIT2
         INY
STRLIT2  TYA
         PHA
         TXA
         PHA
         LDA  HDRFLAG
         BNE  PRSTR
         RTS
*
*--------------------------------------
* PRSTR: PRINT THE STRING ACCUMULATOR.
*--------------------------------------
PRSTR    LDY  #$00                      ;THE LENGTH
         LDA  (STRACC),Y
         STA  ENDCHR
         INY
         STY  HDRFLAG
         LDA  ENDCHR
         BEQ  PRSTR2
PRSTR1   LDY  HDRFLAG                   ;EACH CHARACTER
         LDA  (STRACC),Y
         JSR  OUTDO
         INC  HDRFLAG
         DEC  ENDCHR
         BNE  PRSTR1
PRSTR2   RTS
PRSTR3   BNE  GARBAG6
*
*--------------------------------------
* CLRCHAIN (REM! CLEAR CHAIN) AND FREFN (FRE): BOTH COLLECT GARBAGE.
* CLEAR CHAIN LEAVES THE LOCAL STRINGS OUT, SO ONLY THE COMMON
* STRINGS SURVIVE, PACKED AT THE TOP OF STRING SPACE, FOR THE NEXT
* PROGRAM; IT THEN GOES ON INTO CLEAR, WHICH CLEARS THE LOCAL
* VARIABLES.
*--------------------------------------
CLRCHAIN LDA  LOCSEND+1                 ;KEEP THE LOCAL STRING END'S HIGH BYTE ...
         PHA
         LDA  #$00                      ;... AND MAKE IT 0: NO LOCAL STRINGS ARE KEPT
         STA  LOCSEND+1
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
FREFN    LDA  #$01                      ;FRE: COLLECT, THEN RETURN THE FREE SPACE
*
*--------------------------------------
* GARBAG: THE GARBAGE COLLECTOR. EACH ROUND FINDS THE HIGHEST STRING
* STILL IN USE THAT IS BELOW THE STRINGS ALREADY MOVED, COPIES IT TO
* THE TOP OF STRING SPACE AND REWRITES EVERY POINTER TO IT. THE
* POINTERS ARE THE COMMON STRINGS, THE LOCAL STRINGS AND THE TWO
* STRING ACCUMULATORS. LITERALS IN THE PROGRAM LIE BELOW STRING
* SPACE AND ARE LEFT ALONE.
* FRE RETURNS THE FREE SPACE, FROM THE BOTTOM OF STRINGS DOWN TO THE
* HIGHEST ADDRESS USED BY THE PROGRAM. ERROR $4D, OUT OF MEMORY,
* WHEN A STRING DOES NOT FIT.
*--------------------------------------
GARBAG   PHA                            ;THE MODE: 0 CLEAR CHAIN, 1 FRE, $FF A NEW STRING THAT DID NOT FIT
         LDA  FRETOP                    ;TEMP1 = THE OLD BOTTOM OF STRINGS
         STA  TEMP1
         LDA  FRETOP+1
         STA  TEMP1+1
         LDA  MEMSIZ                    ;THE MOVED STRINGS WILL GROW DOWN FROM HIMEM-2
         SEC
         SBC  #$02
         STA  FRETOP
         STA  TEMP1+2
         LDA  MEMSIZ+1
         SBC  #$00
         STA  FRETOP+1
         STA  TEMP1+3
GARBAG1  LDX  #$00                      ;START A ROUND: THE HIGHEST STRING FOUND SO FAR = NONE
         STX  RESULT+4
         STX  VARNAM+1
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
GARBAG2  LDX  #$12                      ;THE POINTERS: FIRST THE COMMON STRINGS (X = 0), THEN THE LOCAL ONES (X = $12)
         LDA  NUMCEND,X
         SEC
         SBC  #$01
         STA  TPTR
         LDA  NUMCEND+1,X
         SBC  #$00
         STA  TPTR+1
         BNE  GARBAG5
GARBAG3  LDY  #$01                      ;ONE POINTER
         LDA  (TPTR),Y
         BIT  RESULT+4                  ;REWRITING THE POINTERS TO THE STRING JUST MOVED?
         BPL  GARBAG7
         CMP  VARNAM+1
         BNE  GARBAG15
         DEY
         LDA  (TPTR),Y
         CMP  VARNAM
         BNE  GARBAG15
GARBAG4  LDY  #$00                      ;YES: POINT AT ITS NEW PLACE
         LDA  RESULT
         STA  (TPTR),Y
         INY
         LDA  RESULT+1
         STA  (TPTR),Y
         LDA  TPTR
         CMP  SERPNT
         BNE  GARBAG15
         LDA  TPTR+1
         CMP  SERPNT+1
         BEQ  GARBAG1
GARBAG5  BNE  GARBAG15
GARBAG6  BNE  GARBAG20
GARBAG7  CMP  VARNAM+1                  ;SEARCHING: IS THIS STRING HIGHER THAN THE BEST SO FAR?
         BCC  GARBAG15
         BNE  GARBAG9
         DEY
         LDA  (TPTR),Y
         CMP  VARNAM
         BCC  GARBAG15
         BNE  GARBAG9
         LDA  TPTR
         STA  SERPNT
         LDA  TPTR+1
         STA  SERPNT+1
         BCS  GARBAG15
GARBAG8  BNE  GARBAG
GARBAG9  LDY  #$00                      ;AND BELOW THE STRINGS ALREADY MOVED?
         LDA  (TPTR),Y
         CMP  TEMP1+2
         INY
         LDA  (TPTR),Y
         SBC  TEMP1+3
         BCS  GARBAG15
         BCC  GARBAG14
GARBAG10 BMI  GARBAG4
GARBAG11 BCC  GARBAG3
GARBAG12 BEQ  GARBAG2
GARBAG13 BEQ  GARBAG1
GARBAG14 LDA  (TPTR),Y                  ;THE NEW BEST
         STA  VARNAM+1
         DEY
         LDA  (TPTR),Y
         STA  VARNAM
         STX  RESULT+2
         LDA  TPTR
         STA  TEMP3
         STA  SERPNT
         LDA  TPTR+1
         STA  TEMP3+1
         STA  SERPNT+1
GARBAG15 TXA                            ;NEXT POINTER
         BMI  GARBAG22
         LDA  TPTR
         CLC
         ADC  #$02
         STA  TPTR
         BCC  GARBAG16
         INC  TPTR+1
GARBAG16 CMP  STRCEND,X
         LDA  TPTR+1
         SBC  STRCEND+1,X
GARBAG17 BCC  GARBAG11
         TXA
         BEQ  GARBAG12
         LDX  #$80                      ;THEN THE TWO STRING ACCUMULATORS ($77, $79)
         LDA  #$77
         STA  TPTR
         LDA  #$00
         STA  TPTR+1
         CLC
         BCC  GARBAG11
GARBAG18 BMI  GARBAG10
GARBAG19 BNE  GARBAG8
GARBAG20 BNE  GARBAG31
GARBAG21 BEQ  GARBAG13
GARBAG22 LDA  #$79
         CMP  TPTR
         STA  TPTR
         CLC
         BNE  GARBAG17
         LDY  VARNAM                    ;THE ROUND IS OVER
         STY  TEMP1+2
         LDA  VARNAM+1
         BEQ  GARBAG32                  ;NONE FOUND: DONE
         STA  TEMP1+3
         LDX  LOCSEND+1                 ;CLEAR CHAIN: A STRING BELOW THE OLD BOTTOM IS NOT A COMMON STRING TO KEEP
         BEQ  GARBAG23
         CPY  TEMP1
         SBC  TEMP1+1
         BCC  GARBAG32
GARBAG23 LDY  #$00                      ;AN EMPTY STRING: POINT AT THE EMPTY STRING AT HIMEM-1
         LDA  (VARNAM),Y
         BNE  GARBAG25
         LDY  MEMSIZ+1
         LDX  MEMSIZ
         BNE  GARBAG24
         DEY
GARBAG24 DEX
         STX  RESULT
         STY  RESULT+1
         SEC
         BCS  GARBAG29
GARBAG25 CLC                            ;MOVE IT: ROOM BELOW THE BOTTOM OF STRINGS?
         LDA  FRETOP
         SBC  (VARNAM),Y
         TAX
         LDA  FRETOP+1
         SBC  #$00
         TAY
         CPX  HIGHEST                   ;NOT ABOVE THE PROGRAM: OUT OF MEMORY
         SBC  HIGHEST+1
         BCC  GARBAG34
         STX  FRETOP
         STY  FRETOP+1
         INX
         BNE  GARBAG26
         INY
GARBAG26 STX  RESULT
         STY  RESULT+1
         CPX  VARNAM                    ;ALREADY THERE: NOTHING TO COPY
         BNE  GARBAG27
         CPY  VARNAM+1
         BEQ  GARBAG21
GARBAG27 LDY  #$00                      ;COPY THE LENGTH AND THE TEXT
         LDA  (VARNAM),Y
         TAY
GARBAG28 LDA  (VARNAM),Y
         STA  (RESULT),Y
         DEY
         CPY  #$FF
         BNE  GARBAG28
GARBAG29 LDA  TEMP3                     ;NOW REWRITE EVERY POINTER TO IT
         STA  TPTR
         LDA  TEMP3+1
         STA  TPTR+1
         LDX  RESULT+2
         LDA  #$80
         STA  RESULT+4
         BMI  GARBAG18
GARBAG30 BNE  GARBAG19
GARBAG31 BNE  OLDTE2
GARBAG32 SEC                            ;FREE SPACE = BOTTOM OF STRINGS - HIGHEST ADDRESS
         LDA  FRETOP
         SBC  HIGHEST
         TAY
         LDA  FRETOP+1
         SBC  HIGHEST+1
         TAX
         PLA                            ;MODE 1, FRE: RETURN IT IN FAC
         BEQ  GARBAG35
         BMI  GARBAG33
         TXA
         JMP  GIVAYF
GARBAG33 SEC                            ;A NEW STRING: DOES IT FIT NOW?
         TXA
         BNE  GARBAG36
         CPY  CHARAC
         BEQ  GARBAG34
         BCS  GARBAG36
GARBAG34 LDX  #$4D                      ;OUT OF MEMORY: ERROR $4D
         JMP  ERROR
GARBAG35 PLA                            ;CLEAR CHAIN: PUT THE LOCAL STRING END BACK ...
         STA  LOCSEND+1
         LDA  FORPOP                    ;... AND RETURN INTO CLEAR: FORPOP-$107 = $08A9, ONE BEFORE CLEAR, SO THE LOCAL VARIABLES ARE CLEARED AND THE STACK RESET
         SEC
         SBC  #$07
         TAX
         LDA  FORPOP+1
         SBC  #$01
         PHA
         TXA
         PHA
         RTS
GARBAG36 BCS  GETSTR2
*
*--------------------------------------
* OLDTEXT: 45 BYTES OF TEXT LEFT IN MEMORY BY THE ASSEMBLER: NEVER
* EXECUTED. THE BRANCH BEFORE THEM IS ALWAYS TAKEN.
*--------------------------------------
OLDTEXT  DFB  $4C,$45,$3F,$20,$22,$3B,$3A,$B0 ;"LE? ";:0"
         DFB  $31,$31,$32,$30,$3A,$52,$46,$D0 ;"1120:RFP"
         DFB  $32,$3A,$AB,$31,$33,$36,$30,$3A ;"2:+1360:"
         DFB  $B2,$20,$20,$20,$20,$49,$46,$20 ;"2    IF "
         DFB  $41,$20,$44,$49,$53,$4B,$20,$43 ;"A DISK C"
         DFB  $4F,$4D,$4D,$41,$4E       ;"OMMAN"
OLDTE1   BNE  GARBAG30
OLDTE2   BNE  PUSHS2
*
*--------------------------------------
* GETSTR: GET A$: A NEW ONE-CHARACTER STRING FROM THE KEYBOARD.
*--------------------------------------
GETSTR   LDX  #$01                      ;A ONE-BYTE STRING, KIND 5
         LDA  #$05
         BNE  NEWSTR
GETSTR1  JSR  INCHR                     ;THE KEY
         LDY  #$01
         STA  (TPTR),Y
         LDA  #$00
         BEQ  CONCAT4
GETSTR2  BCS  NEWSTR1
*
*--------------------------------------
* CONCAT: THE PUSHED STRING FOLLOWED BY THE LOADED STRING, AS A NEW
* STRING (ERROR $B0, STRING TOO LONG, PAST 255). CONCATT SWAPS THE
* TWO FIRST.
*--------------------------------------
CONCATT  LDA  STRACC                    ;SWAP THE TWO STRINGS
         LDX  STRPSH
         STA  STRPSH
         STX  STRACC
         LDA  STRACC+1
         LDX  STRPSH+1
         STA  STRPSH+1
         STX  STRACC+1
CONCAT   LDY  #$00                      ;THE LOADED STRING EMPTY: THE RESULT IS THE PUSHED ONE
         LDA  (STRACC),Y
         BEQ  PUSHS1
         STA  ENDCHR
         LDA  (STRPSH),Y                ;THE PUSHED STRING EMPTY: THE RESULT IS THE LOADED ONE
         BEQ  PUSHSTR
         CLC                            ;THE TOTAL LENGTH
         ADC  ENDCHR
         BCC  CONCAT1
         LDX  #$B0                      ;PAST 255: STRING TOO LONG, ERROR $B0
         BNE  PUSHS2
CONCAT1  TAX                            ;A NEW STRING, KIND 0
         TYA
         INY
         BNE  NEWSTR
         NOP
         NOP
CONCAT2  LDY  ENDCHR                    ;COPY THE LOADED STRING TO THE END ...
         LDA  (STRACC),Y
         LDY  CHARAC
         STA  (TPTR),Y
         DEC  CHARAC
         DEC  ENDCHR
         BNE  CONCAT2
         LDY  CHARAC
CONCAT3  LDA  (STRPSH),Y                ;... AND THE PUSHED STRING BEFORE IT
         STA  (TPTR),Y
         DEY
         BNE  CONCAT3
CONCAT4  LDA  TPTR                      ;BOTH STRING ACCUMULATORS = THE NEW STRING
         STA  STRACC
         STA  STRPSH
         LDA  TPTR+1
         STA  STRACC+1
         STA  STRPSH+1
         RTS
CONCAT5  BNE  OLDTE1
CONCAT6  BNE  GETSTR1
         NOP
         NOP
*
*--------------------------------------
* PUSHSTR: COPY THE LOADED STRING TO THE PUSHED STRING.
*--------------------------------------
PUSHSTR  LDA  STRACC
         STA  STRPSH
         LDA  STRACC+1
         STA  STRPSH+1
         RTS
PUSHS1   LDA  STRPSH
         STA  STRACC
         LDA  STRPSH+1
         STA  STRACC+1
         RTS
PUSHS2   BNE  NEWSTR4
PUSHS3   BEQ  CONCAT4
*
*--------------------------------------
* NEWSTR: MAKE ROOM FOR A NEW STRING OF {CHARAC} BYTES BELOW THE
* BOTTOM OF STRING SPACE, COLLECTING GARBAGE IF IT DOES NOT FIT, AND
* FILL IT FOR THE CALLER: A SAYS WHICH (0 CONCAT, 1 CHR$, 2 STR$, 3
* LEFT$/MID$, 4 RIGHT$, 5 GET).
*--------------------------------------
NEWSTR   PHA                            ;KEEP THE KIND; $0D = THE LENGTH
         STX  CHARAC
NEWSTR1  LDA  FRETOP                    ;ITS PLACE: BELOW THE BOTTOM OF STRINGS
         SEC
         SBC  CHARAC
         STA  TPTR
         LDA  FRETOP+1
         SBC  #$00
         STA  TPTR+1
         LDA  HIGHEST                   ;ABOVE THE PROGRAM?
         CMP  TPTR
         LDA  HIGHEST+1
         SBC  TPTR+1
         BCC  NEWSTR2
         LDA  #$FF                      ;NO: COLLECT GARBAGE AND TRY AGAIN
         BNE  CONCAT5
NEWSTR2  LDY  #$00                      ;THE LENGTH BYTE
         LDA  CHARAC
         STA  (TPTR),Y
         LDY  TPTR+1                    ;THE NEW BOTTOM OF STRINGS
         LDX  TPTR
         BNE  NEWSTR3
         DEY
NEWSTR3  DEX
         STX  FRETOP
         STY  FRETOP+1
         PLA                            ;FILL IT BY KIND
         TAY
         BEQ  CONCAT2
         DEY
         BEQ  CHRFNI1
         DEY
         BEQ  STRFN3
         DEY
         BEQ  LEFTI4
         DEY
         BEQ  LEFTI6
         BNE  CONCAT6
         NOP
         NOP
         NOP
NEWSTR4  BNE  RIGHTI1
*
*--------------------------------------
* CHR$: A ONE-CHARACTER STRING.
*--------------------------------------
CHRFN    JSR  AYINT
CHRFNI   JSR  CONINT2                   ;THE CHARACTER, A ONE-BYTE STRING, KIND 1
         LDX  #$01
         TXA
         BNE  NEWSTR
CHRFNI1  LDX  IACC+1
         LDY  #$01
         TXA
         STA  (TPTR),Y
         DEY
CHRFNI2  BEQ  PUSHS3
CHRFNI3  BEQ  PUSHSTR
*
*--------------------------------------
* STR$: FOUT CONVERTS FAC TO TEXT AT $0100; THE TEXT BECOMES A NEW
* STRING.
*--------------------------------------
STRFN    JSR  FOUT                      ;THE NUMBER AS TEXT AT $0100
         LDX  #$00                      ;ITS LENGTH
STRFN1   INX
         LDA  STACK,X
         BNE  STRFN1
         LDA  #$02                      ;KIND 2
STRFN2   BNE  NEWSTR
STRFN3   LDY  CHARAC                    ;COPY THE TEXT
STRFN4   LDA  ZPFF,Y
         STA  (TPTR),Y
         DEY
         BNE  STRFN4
         BEQ  CHRFNI2
*
*--------------------------------------
* LEFT$, RIGHT$ AND MID$. THE STRING IS IN THE STRING ACCUMULATOR;
* THE COUNT (AND FOR MID$ THE START, PUSHED BY PUSHBYTE) ARE BYTES.
* A ZERO COUNT IS ERROR $35. WHEN THE RESULT IS THE WHOLE STRING NO
* NEW STRING IS MADE; AN EMPTY RESULT POINTS AT THE EMPTY STRING.
*--------------------------------------
LEFT     JSR  AYINT
LEFTI    JSR  CONINT2                   ;THE COUNT
         TXA
         BNE  LEFTI1
         LDX  #$35                      ;0: ERROR $35
         BNE  RIGHTI1
LEFTI1   LDY  #$00                      ;THE STRING'S LENGTH
         LDA  (STRACC),Y
         BEQ  CHRFNI3
         STA  ENDCHR
LEFTI2   CPX  ENDCHR                    ;THE COUNT COVERS THE WHOLE STRING: KEEP IT
         BCC  LEFTI3
         LDA  #$00
         BEQ  CHRFNI3
LEFTI3   LDA  #$03                      ;OTHERWISE A NEW STRING OF THAT LENGTH, KIND 3
         BNE  STRFN2
LEFTI4   LDY  CHARAC                    ;COPY THE FIRST CHARACTERS
LEFTI5   LDA  (STRACC),Y
         STA  (TPTR),Y
         DEY
         BNE  LEFTI5
         BEQ  CHRFNI2
LEFTI6   BEQ  RIGHTI5
RIGHT    JSR  AYINT
RIGHTI   JSR  CONINT2
         TXA
         BNE  RIGHTI2
         LDX  #$35
RIGHTI1  BNE  MID3I2
RIGHTI2  LDY  #$00
         LDA  (STRACC),Y
RIGHTI3  BEQ  CHRFNI3
         STA  ENDCHR
         CPX  ENDCHR
         BCC  RIGHTI4
         LDA  #$00
         BEQ  RIGHTI3
RIGHTI4  LDA  #$04                      ;A NEW STRING, KIND 4
         BNE  STRFN2
RIGHTI5  SEC                            ;RIGHT$: START AT LENGTH-COUNT
         LDA  ENDCHR
         SBC  CHARAC
         CLC
         ADC  STRACC
         STA  STRACC
         BCC  RIGHTI6
         INC  STRACC+1
RIGHTI6  BNE  LEFTI4
RIGHTI7  BEQ  LEFTI2
RIGHTI8  BCS  LEFTI3
MID2     JSR  AYINT
MID2I    JSR  CONINT2
         LDA  #$FF                      ;MID$ WITHOUT A COUNT: 255
         BNE  MID3I1
MID3     JSR  AYINT
MID3I    JSR  CONINT2
         TXA                            ;MID$ WITH A COUNT: THE START WAS PUSHED IN $10
         LDX  DIMFLG
MID3I1   STA  HDRFLAG
         TXA
         BNE  MID3I3
         LDX  #$35
MID3I2   BNE  MID3I11
MID3I3   LDY  #$00
         LDA  (STRACC),Y
         BEQ  RIGHTI3
         STA  ENDCHR
         TXA
         LDX  HDRFLAG
         BNE  MID3I6
MID3I4   LDY  MEMSIZ+1                  ;THE START IS PAST THE END: THE EMPTY STRING
         LDX  MEMSIZ
         BNE  MID3I5
         DEY
MID3I5   DEX
         STX  STRACC
         STY  STRACC+1
         LDA  #$00
         BEQ  RIGHTI3
MID3I6   SEC                            ;START-1
         SBC  #$01
         BEQ  RIGHTI7
         STA  RESULT+2
         CMP  ENDCHR
         BCS  MID3I4
         ADC  HDRFLAG                   ;START+COUNT PAST THE END?
         BCS  MID3I7
         CMP  ENDCHR
         BCC  MID3I8
MID3I7   LDA  ENDCHR                    ;THEN TO THE END
         SBC  RESULT+2
         TAX
         BNE  RIGHTI4
MID3I8   STA  ENDCHR
         BNE  RIGHTI4
MID3I9   BCS  RIGHTI8
MID3I10  BEQ  MID3I4
MID3I11  BNE  INPST9
*
*--------------------------------------
* INPUT. INPSTR AND INPNUM READ THE FIRST ITEM (PRINTING "?"), THE P
* ENTRIES THE FIRST ITEM AFTER A PROMPT, THE N ENTRIES THE NEXT
* ITEMS. A NEW LINE IS READ WITH INLIN INTO $0200 WHEN NEEDED; $71
* IS THE POSITION IN IT ($FF A NEW LINE, $FE USED UP).
* STRINGS MAY BE QUOTED; ITEMS ARE SEPARATED BY COMMAS. A NUMBER IS
* CONVERTED BY FIN; A BAD ONE PRINTS ?REENTER AND THE WHOLE
* STATEMENT STARTS AGAIN AT THE ADDRESS INPBEG SAVED. CONTROL-C AS
* THE LINE'S FIRST CHARACTER STOPS THE PROGRAM.
*--------------------------------------
MID3I12  JSR  OUTQUES                   ;ENTRY AFTER ?REENTER FOR A STRING
INPSTR   JSR  OUTQUES                   ;PRINT ?
INPSTRP  JSR  INLIN                     ;READ A LINE
         LDA  INBUF                     ;CONTROL-C FIRST: STOP
         CMP  #$03
         BEQ  INPNU1
         LDA  #$FF                      ;A NEW LINE: POSITION $FF
         STA  INPOS
INPSTRN  LDA  INPOS                     ;THE LINE IS USED UP: ASK FOR MORE
         CMP  #$FE
         BEQ  MID3I12
         TAX
INPST1   INX                            ;SKIP SPACES
         LDA  INBUF,X
         CMP  #$20
         BEQ  INPST1
         CMP  #$22                      ;A QUOTED STRING ENDS AT THE QUOTE ...
         BEQ  INPST2
         LDY  #$2C                      ;... ANOTHER AT A COMMA
         STY  HDRFLAG
         BNE  INPST3
INPST2   STA  HDRFLAG
         INX
         LDA  INBUF,X
INPST3   STX  ENDCHR
         LDY  ENDCHR
         LDX  #$00
INPST4   CMP  #$00                      ;FIND THE END OF THE ITEM
         BEQ  INPST7
         CMP  HDRFLAG
         BEQ  INPST5
         INY
         LDA  INBUF,Y
         INX
         BNE  INPST4
INPST5   CMP  #$2C                      ;AFTER A QUOTE: SKIP SPACES TO THE COMMA OR THE END
         BEQ  INPST8
INPST6   INY
         LDA  INBUF,Y
         CMP  #$20
         BEQ  INPST6
         CMP  #$00
         BEQ  INPST7
         CMP  #$2C
         BNE  INPNU4                    ;ANYTHING ELSE: ?REENTER
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
INPST7   LDY  #$FE                      ;THE LINE IS USED UP
INPST8   STY  INPOS                     ;THE NEXT POSITION
         TXA
         BEQ  MID3I10
         CLC                            ;THE ITEM IS IN THE INPUT BUFFER: $77/$78 POINTS AT THE BYTE BEFORE IT, THE LENGTH
         LDA  #$FF
         ADC  ENDCHR
         STA  STRACC
         LDA  #$01
         ADC  #$00
         STA  STRACC+1
         SEC
         BCS  MID3I9
INPST9   BNE  INPNU2
INPST10  JSR  OUTQUES                   ;ENTRY AFTER ?REENTER FOR A NUMBER
INPNUM   JSR  OUTQUES
INPNUMP  JSR  INLIN
         LDA  INBUF
         CMP  #$03
         BNE  INPNU3
INPNU1   LDX  #$FF                      ;CONTROL-C: X = $FF, A BREAK
INPNU2   BNE  PGMEND3
INPNU3   LDA  #$FF
         STA  INPOS
INPNUMN  LDX  INPOS                     ;THE LINE IS USED UP: ASK FOR MORE
         CPX  #$FE
         BEQ  INPST10
         INX                            ;TXTPTR = THE ITEM IN THE BUFFER AT $0200
         STX  TXTPTR
         STX  HDRFLAG
         LDA  #$02
         STA  TXTPTR+1
         JSR  CHRGOT
         JSR  FIN                       ;FIN CONVERTS IT
         LDX  TXTPTR                    ;NOTHING READ: ?REENTER
         CPX  HDRFLAG
         BEQ  INPNU4
         JSR  CHRGOT
         TAY
         BEQ  INPNU5                    ;THE END OF THE LINE ...
         CMP  #$2C                      ;... OR A COMMA
         BEQ  INPNU6
INPNU4   JSR  REENTER                   ;?REENTER, OR THE ONERR ERROR $FE
         NOP                            ;FOUR BYTES THAT DO NOTHING
         NOP
         NOP
         NOP
         PLA                            ;DROP THE RETURN ADDRESS AND START THE INPUT STATEMENT AGAIN AT THE ADDRESS INPBEG SAVED
         PLA
         JMP  (LINNUM)
INPNU5   LDA  #$FE                      ;THE LINE IS USED UP
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
INPNU6   LDA  TXTPTR
         STA  INPOS
         RTS
*
*--------------------------------------
* STOP: PRINT BREAK IN AND THE OBJECT ADDRESS OF THE STOP, THEN END.
*--------------------------------------
STOP     PLA                            ;THE STATEMENT'S OBJECT ADDRESS = RETURN ADDRESS - 2
         SEC
         SBC  #$02
         STA  CURLIN
         PLA
         SBC  #$00
         STA  CURLIN+1
         LDA  #$5D                      ;"BREAK" FROM THE ROM ($D35D)
         LDY  #$D3
         JSR  STROUT
         JSR  INPRT                     ;" IN " AND THE ADDRESS
         JSR  CRDO
*
*--------------------------------------
* PGMEND (END, AND NEW): PUT CHRGET BACK FROM THE ROM, MAKE THE
* PROGRAM SPACE AN EMPTY PROGRAM AND GO BACK TO THE INTERPRETER.
*--------------------------------------
PGMEND   LDX  #$17                      ;PUT THE ROM'S CHRGET BACK AT $B1-$C8
PGMEND1  LDA  CHRGIMG,X
         STA  CHRGET,X
         DEX
         BPL  PGMEND1
         LDY  TXTTAB+1                  ;AN EMPTY PROGRAM: A ZERO BEFORE TXTTAB ...
         LDX  TXTTAB
         BNE  PGMEND2
         DEY
PGMEND2  DEX
         STX  RESULT
         STY  RESULT+1
         LDY  #$00
         TYA
         STA  (RESULT),Y
         CLC
         JSR  SCRTCH                    ;... NEW, THEN BACK TO THE INTERPRETER
         JMP  RUNCLR
PGMEND3  BNE  READN2
*
*--------------------------------------
* INPEND: THE END OF AN INPUT STATEMENT: ?EXTRA IGNORED IF THE LINE
* HAS MORE.
*--------------------------------------
INPEND   LDA  INPOS                     ;THE LINE USED UP?
         CMP  #$FE
         BEQ  INPEND1
         LDA  #$DF                      ;NO: ?EXTRA IGNORED ($DCDF)
         LDY  #$DC
         JSR  STROUT
         LDA  #$FE
         STA  INPOS
INPEND1  RTS
*
*--------------------------------------
* GETNUM: GET X: A DIGIT KEY GIVES ITS VALUE, ANY OTHER KEY 0.
*--------------------------------------
GETNUM   JSR  INCHR                     ;THE KEY
         SBC  #$30                      ;A DIGIT GIVES ITS VALUE ...
         BCC  GETNUM1
         CMP  #$0A
         BCC  GETNUM2
GETNUM1  LDA  #$00                      ;... ANYTHING ELSE 0
GETNUM2  JMP  FLOAT
*
*--------------------------------------
* READ. THE DATA POINTER WALKS THE DATA ITEMS IN THE CODE: EACH IS A
* LENGTH BYTE AND ITS TEXT; $FF IS FOLLOWED BY THE ADDRESS OF THE
* NEXT DATA BLOCK (0 AFTER THE LAST: ERROR $2A, OUT OF DATA). A
* STRING ITEM IS USED IN PLACE; A NUMBER IS CONVERTED BY FIN (ERROR
* $10, SYNTAX, IF ANYTHING IS LEFT).
*--------------------------------------
READSTR  LDA  #$01                      ;A STRING ITEM ...
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
READNUM  LDA  #$00                      ;... OR A NUMBER
         PHA
READN1   LDA  DATPTR+1                  ;NO DATA LEFT: OUT OF DATA, ERROR $2A
         BNE  READN3
         PLA
         LDX  #$2A
READN2   BNE  READN7
READN3   LDY  #$00                      ;THE ITEM'S LENGTH, OR $FF
         LDA  (DATPTR),Y
         STA  HDRFLAG
         CMP  #$FF
         BNE  READN5
         INC  DATPTR                    ;$FF: GO TO THE NEXT DATA BLOCK
         BNE  READN4
         INC  DATPTR+1
READN4   LDA  (DATPTR),Y
         TAX
         INY
         LDA  (DATPTR),Y
         STX  DATPTR
         STA  DATPTR+1
         DEY
         BEQ  READN1
READN5   LDX  DATPTR                    ;THE ITEM
         LDY  DATPTR+1
         PLA
         BEQ  READN6
         STX  STRACC                    ;A STRING: USED WHERE IT IS
         STY  STRACC+1
         BNE  READN8
READN6   STX  TXTPTR                    ;A NUMBER: TXTPTR = THE ITEM ...
         STY  TXTPTR+1
         LDY  HDRFLAG                   ;... WITH A ZERO AFTER IT FOR NOW
         INY
         LDA  (DATPTR),Y
         PHA
         LDA  #$00
         STA  (DATPTR),Y
         JSR  CHRGET                    ;FIN CONVERTS IT
         JSR  FIN
         JSR  CHRGOT                    ;ANYTHING LEFT?
         TAX
         LDY  HDRFLAG
         INY
         PLA
         STA  (DATPTR),Y
         TXA
         BEQ  READN8
         LDX  #$10                      ;SYNTAX ERROR, $10
READN7   BNE  ERREXIT
READN8   SEC                            ;THE DATA POINTER PASSES THE ITEM
         LDA  DATPTR
         ADC  HDRFLAG
         STA  DATPTR
         BCC  READN9
         INC  DATPTR+1
READN9   RTS
*
*--------------------------------------
* ERREXIT: EVERY LIBRARY ERROR ENDS HERE WITH THE ERROR NUMBER IN X.
* WITHOUT ONERR THE OBJECT ADDRESS OF THE CALL THAT FAILED BECOMES
* THE LINE NUMBER OF THE MESSAGE. X = $FF IS A CONTROL-C BREAK.
*--------------------------------------
ERREXIT  LDA  ERRFLG                    ;ONERR ACTIVE?
         BEQ  DEBUG1
ERREX1   CPX  #$FF                      ;X = $FF: A CONTROL-C BREAK
         BEQ  ERREX2
         JMP  ERROR                     ;ERROR X
ERREX2   LDA  #$03
         JMP  STOPCC
*
*--------------------------------------
* DEBUG: CALLED BEFORE EACH STATEMENT WITH THE RESUME/DEBUG OPTION.
* IT KEEPS THE STACK POINTER AND THE STATEMENT'S OBJECT ADDRESS, SO
* THAT AFTER AN ERROR RESUME CAN START THE STATEMENT AGAIN.
*--------------------------------------
DEBUG    TSX                            ;THE STACK POINTER BEFORE THE CALL
         INX
         INX
         STX  REMSTK
         TXA
DEBUG1   STA  HDRFLAG                   ;A = 0 FROM ERREXIT
         PLA                            ;CURLIN = RETURN ADDRESS - 2, THE OBJECT ADDRESS OF THE STATEMENT (OR OF THE CALL THAT FAILED)
         TAY
         SEC
         SBC  #$02
         STA  CURLIN
         PLA
         PHA
         SBC  #$00
         STA  CURLIN+1
         TYA
         PHA
         LDA  HDRFLAG                   ;FROM ERREXIT: ON TO THE ERROR
         BEQ  ERREX1
         RTS
*
*--------------------------------------
* STATEMENTS WITH ONE BYTE ARGUMENT: PR#, IN#, POKE (THE VALUE),
* WAIT (THE MASKS), TAB(, SPC(. THE REAL ENTRY CONVERTS FAC WITH
* AYINT; THE INTEGER ENTRY, 3 BYTES LATER, TAKES THE BYTE WITH
* CONINT (ERROR $35 PAST 255).
*--------------------------------------
PRNUM    JSR  AYINT
PRNUMI   JSR  CONINT2
         JMP  PRSLOT                    ;THE ROM'S PR#
INNUM    JSR  AYINT
INNUMI   JSR  CONINT2
         JMP  INSLOT
POKE     JSR  AYINT
POKEI    JSR  CONINT2
         JMP  POKE2
WAIT     JSR  AYINT
WAITI    JSR  CONINT2
         STX  FORPNT                    ;WAIT WITH TWO ARGUMENTS: THE MASK, NO XOR VALUE
         LDX  #$00
         BEQ  WAIT3I1
WAIT3    JSR  AYINT
WAIT3I   JSR  CONINT2
WAIT3I1  JMP  WAIT2                     ;THE ROM'S WAIT
TAB      JSR  AYINT
TABI     JSR  CONINT2
         DEX                            ;TAB(N): N-1 - CURSOR COLUMN SPACES
         TXA
         SEC
         SBC  CH
         BCC  COMMA2
         TAX
         BCS  SPCI2
SPC      JSR  AYINT
SPCI     JSR  CONINT2
         INX                            ;SPC(N): N SPACES
SPCI1    DEX
SPCI2    BEQ  COMMA2
         JSR  OUTSP
         BNE  SPCI1
*
*--------------------------------------
* COMMA: A COMMA IN PRINT: TO THE NEXT 16-COLUMN FIELD, OR A NEW
* LINE PAST COLUMN 24.
*--------------------------------------
COMMA    LDA  CH                        ;PAST COLUMN 24: A NEW LINE
         CMP  #$18
         BCC  COMMA1
         JMP  CRDO
COMMA1   ADC  #$10                      ;TO THE NEXT MULTIPLE OF 16
         AND  #$F0
         STA  CH
COMMA2   RTS
VTAB     JSR  AYINT
VTABI    JSR  CONINT2
         JMP  VTAB2
HTAB     JSR  AYINT
HTABI    JSR  CONINT2
         JMP  HTAB2
*
*--------------------------------------
* ON ... GOTO AND ON ... GOSUB: THE CALL IS FOLLOWED BY THE NUMBER
* OF LINES AND THEIR ADDRESSES. AN INDEX OF 0 OR PAST THE LIST GOES
* ON AFTER THE LIST; OTHERWISE CONTROL GOES TO THE LINE, FOR GOSUB
* WITH A RETURN ADDRESS PAST THE LIST.
*--------------------------------------
ONGOTO   JSR  AYINT
ONGOTOI  LDX  #$00                      ;X = 0: GOTO
         BEQ  ONGOS1
ONGOSUB  JSR  AYINT
ONGOSUBI LDX  #$01                      ;X = 1: GOSUB
ONGOS1   STX  HDRFLAG
         JSR  CONINT2                   ;THE INDEX
         PLA                            ;THE RETURN ADDRESS POINTS AT THE COUNT - 1
         STA  LINNUM
         PLA
         STA  LINNUM+1
         LDY  #$01                      ;THE COUNT
         LDA  (LINNUM),Y
         TAY
         ASL                            ;RETURN ADDRESS PAST THE LIST: COUNT*2+1
         SEC
         ADC  LINNUM
         TAX
         LDA  LINNUM+1
         ADC  #$00
         PHA
         TXA
         PHA
         TYA                            ;INDEX 0 OR ABOVE THE COUNT: CONTINUE AFTER THE LIST
         CMP  IACC+1
         BCC  ONGOS2
         LDA  IACC+1
         BNE  ONGOS3
ONGOS2   RTS
ONGOS3   LDX  HDRFLAG                   ;GOTO: DROP THE RETURN ADDRESS; GOSUB KEEPS IT
         BNE  ONGOS4
         PLA
         PLA
ONGOS4   LDA  IACC+1                    ;THE LINE'S ADDRESS - 1 ...
         ASL
         TAY
         LDA  (LINNUM),Y
         TAX
         INY
         LDA  (LINNUM),Y
         TAY
         TXA
         BNE  ONGOS5
         DEY
ONGOS5   DEX
         TYA                            ;... PUSHED, AND RTS GOES THERE
         PHA
         TXA
         PHA
         RTS
*
*--------------------------------------
* AND, OR AND THE RELATIONS. THE CODE BEFORE THE CALL HAS SET THE
* FLAGS: FOR AND/OR BY LOADING ONE OPERAND, FOR A RELATION BY
* COMPARING (A = -1, 0, 1). THE RESULT IN FAC IS 1 (TRUE) OR 0
* (FALSE). THE ENTRIES SHARE CODE BY FALLING THROUGH ONE ANOTHER.
*--------------------------------------
LOGORI   ORA  IACC+1                    ;INTEGER OR: EITHER OPERAND NOT ZERO
         ORA  IACC
         BNE  RELTRUE
LOGANDI  BEQ  RELFALSE                  ;INTEGER AND: BOTH NOT ZERO
         LDA  IACC+1
         ORA  IACC
         BEQ  RELFALSE
LOGOR    BNE  RELTRUE                   ;REAL OR
         LDA  FAC
         BNE  RELTRUE
LOGAND   BEQ  RELFALSE                  ;REAL AND
         LDA  FAC
         BEQ  RELFALSE
RELNE    BNE  RELTRUE
RELGT    BEQ  RELFALSE
RELGE    BMI  RELFALSE
RELTRUE  LDA  #$13                      ;TRUE: FAC = 1.0 (THE ROM'S CONSTANT AT $E913)
         LDY  #$E9
         JMP  MOVFM
RELEQ    BNE  RELFALSE
RELLE    BEQ  RELTRUE
RELLT    BMI  RELTRUE
RELFALSE LDA  #$00                      ;FALSE: FAC = 0
         STA  FAC
         RTS
*
*--------------------------------------
* STRING RELATIONS ON THE PUSHED STRING (LEFT) AND THE LOADED STRING
* (RIGHT). STRLT AND STRGE SWAP THEM AND USE THE CODE OF STRGT AND
* STRLE. EQUAL OR NOT EQUAL COMPARE LENGTHS FIRST.
*--------------------------------------
STRGE    LDA  #$01                      ;STRGE: STRLE WITH THE STRINGS SWAPPED
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
STRLT    LDA  #$00                      ;STRLT: STRGT WITH THE STRINGS SWAPPED
         LDY  STRACC
         LDX  STRPSH
         STY  STRPSH
         STX  STRACC
         LDY  STRACC+1
         LDX  STRPSH+1
         STY  STRPSH+1
         STX  STRACC+1
         BNE  STRGT1
STRLE    LDA  #$01                      ;STRLE: NOT GREATER
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
STRGT    LDA  #$00                      ;STRGT
STRGT1   PHA
         LDY  #$00                      ;COMPARE UP TO THE SHORTER LENGTH
         LDA  (STRPSH),Y
         CMP  (STRACC),Y
         BEQ  STRGT2
         BCC  STRGT2
         LDA  (STRACC),Y
         TAX
         INY
         STY  RESULT+4
         BNE  STRGT3
STRGT2   STY  RESULT+4
         INY
         TAX
STRGT3   TXA
         BEQ  STRGT5
STRGT4   LDA  (STRPSH),Y
         CMP  (STRACC),Y
         BCC  STRGT6
         BNE  STRGT8
         INY
         DEX
         BNE  STRGT4
STRGT5   LDA  RESULT+4                  ;ALL EQUAL: THE LONGER STRING IS GREATER
         BNE  STRGT8
STRGT6   PLA
         BNE  STREQ5
STRGT7   LDA  #$00
         STA  FAC
         RTS
STRGT8   PLA
         BNE  STRGT7
         BEQ  STREQ5
STREQ    LDA  #$00                      ;STREQ
STREQ1   PHA
         LDA  STRACC                    ;THE SAME STRING: EQUAL
         CMP  STRPSH
         BNE  STREQ2
         LDA  STRACC+1
         CMP  STRPSH+1
         BEQ  STREQ4
STREQ2   LDY  #$00                      ;THE SAME LENGTH ...
         LDA  (STRACC),Y
         CMP  (STRPSH),Y
         BNE  STREQ6
         TAY
         BEQ  STREQ4
STREQ3   LDA  (STRACC),Y                ;... AND THE SAME CHARACTERS
         CMP  (STRPSH),Y
         BNE  STREQ6
         DEY
         BNE  STREQ3
STREQ4   PLA
         BNE  STREQ7
STREQ5   LDA  #$13
         LDY  #$E9
         JMP  MOVFM
STREQ6   PLA
         BNE  STREQ5
STREQ7   LDA  #$00
         STA  FAC
         RTS
STRNE    LDA  #$01                      ;STRNE
         BNE  STREQ1
*
*--------------------------------------
* STATEMENTS AND ARGUMENTS THAT KEEP A BYTE FOR LATER: ROT=, SCALE=,
* THE SHAPE NUMBER, THE THIRD WAIT ARGUMENT, A BYTE FOR SCRN( OR
* MID$, THE HI-RES X (16 BITS, SAVEHX), HCOLOR=, THE LO-RES X
* (SAVEX) AND THE OTHER END OF HLIN/VLIN (SAVEY), SPEED=.
*--------------------------------------
ROT      JSR  AYINT
ROTI     JSR  CONINT2
         STX  HGRROT                    ;ROTATION
         RTS
SCALE    JSR  AYINT
SCALEI   JSR  CONINT2
         STX  HGRSCALE                  ;SCALE
         RTS
SVSHAPE  JSR  AYINT
SVSHAPEI JSR  CONINT2
         STX  FIRST                     ;SHAPE NUMBER
         RTS
SVARG3   JSR  AYINT
SVARG3I  JSR  CONINT2
         STX  FORPNT                    ;THIRD ARGUMENT OF WAIT
         RTS
PUSHBYTE JSR  AYINT
PUSHBYTI JSR  CONINT2
         STX  DIMFLG                    ;FIRST ARGUMENT OF SCRN( OR THE START OF MID$
         RTS
SAVEHX   JSR  AYINT
SAVEHXI  LDA  IACC                      ;HI-RES X, 16 BITS, TO $50/$51
         STA  LINNUM+1
         LDA  IACC+1
         STA  LINNUM
         RTS
HCOLOR   JSR  AYINT
HCOLORI  JSR  CONINT2
         JMP  HCOLOR2                   ;THE ROM'S HCOLOR=
SAVEX    JSR  AYINT
SAVEXI   JSR  CONINT2
         STX  FIRST                     ;LO-RES X
         JMP  PLOTCHK
SAVEY    JSR  AYINT
SAVEYI   JSR  CONINT2
         JSR  LINCHK                    ;HLIN/VLIN: ORDER THE TWO ENDS
         CPX  FIRST
         BCS  SAVEYI1
         LDA  FIRST
         STA  H2
         STA  V2
         STX  FIRST
SAVEYI1  RTS
SPEED    JSR  AYINT
SPEEDI   JSR  CONINT2
         JMP  SPEED2
*
*--------------------------------------
* INPBEG: THE START OF AN INPUT STATEMENT: KEEP ITS OBJECT ADDRESS
* FOR ?REENTER.
*--------------------------------------
INPBEG   PLA                            ;RETURN ADDRESS - 2: THE INPUT STATEMENT'S ADDRESS, FOR ?REENTER
         TAX
         SEC
         SBC  #$02
         STA  LINNUM
         PLA
         PHA
         SBC  #$00
         STA  LINNUM+1
         TXA
         PHA
         RTS
*
*--------------------------------------
* ONERR: THE CALL IS FOLLOWED BY THE HANDLER'S ADDRESS, WHICH GOES
* INTO THE ONERR VECTOR AT $5B.
*--------------------------------------
ONERR    LDX  #$80                      ;ONERR ON
         STX  ERRFLG
         PLA                            ;RETURN PAST THE INLINE WORD
         STA  RESULT
         CLC
         ADC  #$02
         TAX
         PLA
         STA  RESULT+1
         ADC  #$00
         PHA
         TXA
         PHA
         LDY  #$01                      ;THE HANDLER'S ADDRESS INTO THE ONERR VECTOR
         LDA  (RESULT),Y
         STA  ERRVEC+1
         INY
         LDA  (RESULT),Y
         STA  ERRVEC+2
         RTS
*
*--------------------------------------
* RESUME: BACK TO THE STATEMENT THAT FAILED (ITS DEBUG CALL) WITH
* THE STACK AS IT WAS.
*--------------------------------------
RESUME   LDX  ERRSTK                    ;THE STACK AS IT WAS BEFORE THE STATEMENT
         TXS
         JMP  (ERRLIN)                  ;AND BACK TO THE STATEMENT'S DEBUG CALL
*
*--------------------------------------
* PUSHSUB: PUSH A SUBSCRIPT UNDER THE RETURN ADDRESS FOR THE ARRAY
* ROUTINE.
*--------------------------------------
PUSHSUB  JSR  AYINT
PUSHSUBI PLA                            ;PUSH IACC UNDER THE RETURN ADDRESS
         TAX
         PLA
         TAY
         LDA  IACC
         PHA
         LDA  IACC+1
         PHA
         TYA
         PHA
         TXA
         PHA
         RTS
*
*--------------------------------------
* FLOATI: FAC = IACC. THE JMP AT $58 COMES HERE. IMOVE: IARG = IACC.
*--------------------------------------
FLOATI   LDA  IACC
         LDY  IACC+1
         JMP  GIVAYF
IMOVE    LDA  IACC
         STA  IARG
         LDA  IACC+1
         STA  IARG+1
         RTS
*
*--------------------------------------
* LOOP LIMIT AND STEP, CALLED AFTER THE LOOP START. THEY PUT THE
* VALUES INTO THE FRAME UNDER THE CALLER'S RETURN ADDRESS; THE LIMIT
* ALSO PUSHES THE LOOP ADDRESS (THE RETURN ADDRESS OF THE STEP CALL)
* AND THE MARKER. INTEGER LOOPS: IFORLIM, IFORSTEP (IFORST1 = STEP
* 1); REAL LOOPS: FORLIM, FORSTEP (FORSTEP1 = STEP 1). THE R AND I
* ENTRIES CONVERT THE VALUE FIRST.
*--------------------------------------
IFORST1  LDX  #$01                      ;IACC = 1
         STX  IACC+1
         DEX
         STX  IACC
         BEQ  IFORSTEP
IFORSTR  JSR  AYINT
IFORSTEP LDA  #$00                      ;STEP: A = 0
         BEQ  IFORL1
IFORLIMR JSR  AYINT
IFORLIM  LDA  #$01                      ;LIMIT: A = 1
IFORL1   STA  HDRFLAG
         PLA                            ;THE RETURN ADDRESS
         STA  RESULT+2
         PLA
         STA  RESULT+3
         PHA                            ;PUT IT BACK TWICE
         LDA  RESULT+2
         PHA
         PHA
         LDA  IACC+1                    ;AND THE INTEGER VALUE
         PHA
         LDA  IACC
         PHA
         LDA  HDRFLAG                   ;THE LIMIT ALSO PUSHES THE MARKER
         BEQ  FORPU1
         BNE  FORPU2
FORSTEP1 LDY  #$E9                      ;STEP 1.0 (THE ROM'S CONSTANT AT $E913)
         LDA  #$13
         JSR  MOVFM
         BNE  FORSTEP
FORSTEPI JSR  FLTVEC
FORSTEP  LDA  #$00                      ;STEP: A = 0
         BEQ  FORPUSH
FORLIMI  JSR  FLTVEC
FORLIM   LDA  #$01                      ;LIMIT: A = 1
FORPUSH  STA  HDRFLAG
         TSX                            ;MAKE ROOM FOR 5 BYTES UNDER THE RETURN ADDRESS ...
         DEX
         DEX
         DEX
         PLA
         STA  RESULT+2
         PLA
         STA  RESULT+3
         TXS
         INX
         LDY  #$01                      ;... AND STORE FAC THERE
         JSR  MOVMF
         LDA  HDRFLAG
         BNE  FORPU2
         LDA  RESULT+3                  ;THE LOOP ADDRESS AND THE MARKER
FORPU1   PHA
         LDA  RESULT+2
         PHA
         LDA  FORPOP+1
         PHA
         LDA  FORPOP
         PHA
FORPU2   LDA  RESULT+3                  ;RETURN
         PHA
         LDA  RESULT+2
         PHA
         RTS
*
*--------------------------------------
* SCRN(: THE FIRST ARGUMENT WAS PUSHED WITH PUSHBYTE. POS: THE
* CURSOR COLUMN. THE RESULT GOES TO IACC.
*--------------------------------------
SCRN     JSR  AYINT
SCRNI    JSR  CONINT2
         JSR  PLOTCHK                   ;X: 0-47
         TXA
         LDX  DIMFLG
         JSR  PLOTCHK                   ;Y: 0-47
         LDY  DIMFLG
         JSR  MONSCRN                   ;THE ROM'S SCRN
         DFB  $2C                       ;BIT ABSOLUTE: SKIPS THE NEXT 2 BYTES
POS      LDA  CH                        ;POS: THE CURSOR COLUMN
POS1     STA  IACC+1                    ;IACC = A
         LDY  #$00
         STY  IACC
         TAY
         RTS
*
*--------------------------------------
* PLOT, HLIN, VLIN, PDL: THE LAST ARGUMENT; THE OTHERS WERE SAVED
* BEFORE. PDL GIVES ITS RESULT IN IACC.
*--------------------------------------
PLOT     JSR  AYINT
PLOTI    JSR  CONINT2
         JSR  PLOTCHK
         JMP  PLOT2
HLIN     JSR  AYINT
HLINI    JSR  CONINT2
         JSR  PLOTCHK
         JMP  HLIN2
VLIN     JSR  AYINT
VLINI    JSR  CONINT2
         JMP  VLIN2
PDL      JSR  AYINT
PDLI     JSR  CONINT2
         JSR  PREAD                     ;READ THE PADDLE
PDLI1    TYA
         SEC
         BCS  POS1
*
*--------------------------------------
* STATEMENTS AND FUNCTIONS WITH AN ADDRESS: CALL, POKE AND WAIT (THE
* ADDRESS, SVADDR), PEEK. GETADR TAKES ANY VALUE FROM -65535 TO
* 65535. THE INTEGER ENTRY, 3 BYTES EARLIER, FLOATS IACC FIRST, SO
* -16384 IS A GOOD ADDRESS.
*--------------------------------------
CALLI    JSR  FLTVEC
CALL     JMP  CALLROM                   ;THE ROM'S CALL
SVADDRI  JSR  FLTVEC
SVADDR   JMP  GETADR                    ;THE ADDRESS TO $50/$51
PEEKI    JSR  FLTVEC
PEEK     LDA  LINNUM+1                  ;PEEK KEEPS $50/$51 (THE POKE ADDRESS)
         PHA
         LDA  LINNUM
         PHA
         JSR  GETADR
         LDY  #$00                      ;THE BYTE
         LDA  (LINNUM),Y
         TAY
         PLA
         STA  LINNUM
         PLA
         STA  LINNUM+1
         SEC
         BCS  PDLI1
*
*--------------------------------------
* PRINT A NUMBER: PRINTI FLOATS IACC FIRST.
*--------------------------------------
PRINTI   JSR  FLTVEC
PRINTN   JMP  PRNTFAC                   ;THE ROM PRINTS FAC
*
*--------------------------------------
* DISPREAL: THE REAL VARIABLE DISPATCHER: X = OPERATION, (Y,A) = THE
* VARIABLE. 0 LOAD FAC (AND SET THE FLAGS), 1 STORE FAC, 2 ADD, 3
* VARIABLE MINUS FAC, 4 MULTIPLY, 5 COMPARE, 6 LOAD ARG, 7 VARIABLE
* DIVIDED BY FAC.
*--------------------------------------
DISPREAL DEX                            ;OPERATION 0
         BMI  DISPR7
         BNE  DISPR1                    ;1: STORE FAC ROUNDED AT (Y,X)
         TAX
         JMP  MOVMF
DISPR1   DEX                            ;2 ADD
         BEQ  DISPR5
         DEX                            ;3 SUBTRACT
         BEQ  DISPR4
         DEX                            ;4 MULTIPLY
         BEQ  DISPR3
         DEX                            ;5 COMPARE
         BEQ  DISPR2
         DEX                            ;6 LOAD ARG
         BEQ  DISPR6
         JMP  FDIV                      ;7 DIVIDE
DISPR2   JMP  FCOMP
DISPR3   JMP  FMULT
DISPR4   JMP  FSUB
DISPR5   JMP  FADD
DISPR6   JMP  CONUPK
DISPR7   JSR  MOVFM                     ;LOAD FAC; SIGNS COMPARED; A = THE EXPONENT (FLAGS SET)
         LDA  ARGSIGN
         JMP  SGNEXIT
*
*--------------------------------------
* COPYRT: THE COPYRIGHT NOTICE.
*--------------------------------------
COPYRT   DFB  $C3,$CF,$D0,$D9,$D2,$C9,$C7,$C8 ;"COPYRIGH"
         DFB  $D4,$A8,$C3,$A9,$B1,$B9,$B8,$B1 ;"T(C)1981"
         DFB  $AC,$CD,$C9,$C3,$D2,$CF,$D3,$CF ;",MICROSO"
         DFB  $C6,$D4                   ;"FT"
