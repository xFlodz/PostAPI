import grpc
from concurrent import futures
from src.proto import post_pb2, post_pb2_grpc
from ..services.post_service import remove_tag_from_all_posts_service

class gRPCPostService(post_pb2_grpc.gRPCPostServiceServicer):
    def __init__(self, app):
        self.app = app

    def RemoveTagFromPosts(self, request, context):
        with self.app.app_context():
            success = remove_tag_from_all_posts_service(request.tag_id)
            return post_pb2.RemoveTagResponse(success=success)

def run_grpc_server(app):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    post_pb2_grpc.add_gRPCPostServiceServicer_to_server(gRPCPostService(app), server)
    server.add_insecure_port('0.0.0.0:50055')
    print("Post gRPC Server started on port 50055")
    server.start()
    server.wait_for_termination()
