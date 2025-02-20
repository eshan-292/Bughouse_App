from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import chess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Initialize game boards and team reserves.
# In this setup (team assignments):
# • Board 1: white is Team A, black is Team B.
# • Board 2: white is Team B, black is Team A.
board1 = chess.Board()
board2 = chess.Board()
reserve_teamA = []  # For Team A (board1 white and board2 black)
reserve_teamB = []  # For Team B (board1 black and board2 white)

def get_team_reserve(board_num, color):
    """
    Returns the reserve for the player's team, based on the board number and the player's color.
    """
    if board_num == 1:
        return reserve_teamA if color == chess.WHITE else reserve_teamB
    elif board_num == 2:
        return reserve_teamB if color == chess.WHITE else reserve_teamA

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('move')
def handle_move(data):
    board_num = int(data.get('board', 1))
    move_type = data.get('type', 'move')
    board = board1 if board_num == 1 else board2

    if move_type == 'move':
        try:
            move_str = data.get('move')
            # Client should supply the moving player's color ("white" or "black")
            color_str = data.get('color', 'white')
            player_color = chess.WHITE if color_str == 'white' else chess.BLACK

            # Check that it is the player’s turn.
            if board.turn != player_color:
                emit('error', {'message': 'Not your turn'})
                return

            move = chess.Move.from_uci(move_str)
            if move not in board.legal_moves:
                emit('error', {'message': 'Illegal move'})
                return

            # Save captured piece (if any) before making the move.
            captured_piece = board.piece_at(move.to_square)
            board.push(move)
            if captured_piece:
                # When a capture occurs, add it to the partner’s reserve.
                partner_reserve = get_team_reserve(board_num, player_color)
                # Store the piece type as a lowercase letter (e.g. 'p','n','b','r','q')
                partner_reserve.append(captured_piece.symbol().lower())
            
            # Broadcast the updated board state.
            emit('board_update', {
                'board': board_num,
                'fen': board.fen(),
                'reserveA': reserve_teamA,
                'reserveB': reserve_teamB
            }, broadcast=True)
        except Exception as e:
            emit('error', {'message': str(e)})

    elif move_type == 'drop':
        # For drop moves, the client must supply:
        #   • "piece": the piece to drop (one of: p, n, b, r, q)
        #   • "to": the target square (e.g., "e4")
        #   • "color": player's color ("white" or "black")
        piece_letter = data.get('piece')
        target_square_str = data.get('to')
        color_str = data.get('color', 'white')
        player_color = chess.WHITE if color_str == 'white' else chess.BLACK

        team_reserve = get_team_reserve(board_num, player_color)
        if piece_letter not in team_reserve:
            emit('error', {'message': 'Piece not in reserve'})
            return

        target_square = chess.square_from_name(target_square_str)
        if board.piece_at(target_square) is not None:
            emit('error', {'message': 'Target square not empty'})
            return

        # Map a letter to a piece type.
        mapping = {
            'p': chess.PAWN,
            'n': chess.KNIGHT,
            'b': chess.BISHOP,
            'r': chess.ROOK,
            'q': chess.QUEEN,
            'k': chess.KING
        }
        piece_type = mapping.get(piece_letter)
        if not piece_type:
            emit('error', {'message': 'Invalid piece type'})
            return

        # Place the dropped piece on the board.
        board.set_piece_at(target_square, chess.Piece(piece_type, player_color))
        team_reserve.remove(piece_letter)

        emit('board_update', {
            'board': board_num,
            'fen': board.fen(),
            'reserveA': reserve_teamA,
            'reserveB': reserve_teamB
        }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
